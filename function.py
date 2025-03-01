import datetime
import gc
import os
import time
import numpy as np
from osgeo import gdal
from scipy.ndimage import label
from tqdm import tqdm


def run_time(func):
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        elapsed_time = end_time - start_time
        elapsed_time = datetime.timedelta(seconds=int(elapsed_time))
        print(f"run time：{elapsed_time}")
        return result

    return wrapper


@run_time
def read(tiff_path):
    '''读取tif数据、列、行、波段、格式、变换、投影'''
    in_ds = gdal.Open(tiff_path, gdal.GA_ReadOnly)
    if not in_ds:
        raise FileNotFoundError(f"无法打开文件：{tiff_path}")
    try:
        cols, rows, bands = in_ds.RasterXSize, in_ds.RasterYSize, in_ds.RasterCount
        dtype = in_ds.GetRasterBand(1).DataType
        data_type_name = gdal.GetDataTypeName(dtype)
        print(f"驱动: {in_ds.GetDriver().ShortName}")
        print(f"高度(行): {rows}")
        print(f"宽度(列): {cols}")
        print(f"波段数: {bands}")
        print(f"数据类型为: {data_type_name}")
        geo = in_ds.GetGeoTransform()
        proj = in_ds.GetProjection()
        if geo:
            print(f"地理变换：{geo}")
            print(f"-左上角坐标: ({geo[0]}, {geo[3]})")
            print(f"-像素宽度: {geo[1]}")
            print(f"-像素高度: {geo[5]}")
        if proj:
            print(f"投影信息: {proj}")
        data = in_ds.ReadAsArray()
        if data.ndim == 2:
            data = np.expand_dims(data, axis=0)
    finally:
        in_ds = None
    return data, cols, rows, bands, dtype, geo, proj


@run_time
def sliding_clipping_diy(input_path, output_folder, clip_width, clip_height):
    '''这个函数支持自定义矩形裁剪'''
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    in_ds = gdal.Open(input_path)
    filename = os.path.splitext(os.path.basename(input_path))[0]
    # 计算横向和纵向的裁剪数量
    num_cols = in_ds.RasterXSize // clip_width  # 列，x轴方向
    num_rows = in_ds.RasterYSize // clip_height  # 行，y轴方向
    print('num_rows=%d,num_cols=%d' % (num_rows, num_cols))
    geo = in_ds.GetGeoTransform()
    proj = in_ds.GetProjection()
    # 循环裁剪图像
    for x in range(num_cols):
        for y in range(num_rows):
            # 计算当前裁剪窗口的起始和结束位置
            xoff = x * clip_width  # 列，位置，从左往右
            yoff = y * clip_height  # 行，位置，从上往下
            # 读取当前窗口的数据
            bands_data = []
            bands = in_ds.RasterCount
            # 循环遍历所有波段
            for i in range(1, bands + 1):
                band_data = in_ds.GetRasterBand(i).ReadAsArray(xoff, yoff, clip_width, clip_height)  # 读取当前波段的数组数据
                bands_data.append(band_data)  # 将波段数据添加到列表中
            # 构建输出文件名
            out_file = os.path.join(output_folder, f'{filename}_{x}_{y}.tif')
            # 创建裁剪后的图像文件，并设置空间参考和仿射变换参数
            driver = gdal.GetDriverByName('GTiff')
            options = ['COMPRESS={}'.format('LZW')]
            # options = ['COMPRESS={}'.format('LZW'), 'BIGTIFF=YES'] # 压缩大于4G的tif用这个
            out_dataset = driver.Create(out_file, clip_width, clip_height, bands, in_ds.GetRasterBand(1).DataType,
                                        options=options)
            # 设置输出图像的空间参考和仿射变换参数，保持与原始图像一致
            out_dataset.SetGeoTransform(
                (geo[0] + xoff * geo[1], geo[1], 0, geo[3] + yoff * geo[5], 0, geo[5]))  # 设置地理变换
            out_dataset.SetProjection(proj)
            # 写入输出图像数据
            for i, band_data in enumerate(bands_data, start=1):
                out_dataset.GetRasterBand(i).WriteArray(band_data)
            out_dataset.FlushCache()
            out_dataset = None


def write(output_path, data, cols, rows, bands=1, dtype=gdal.GDT_Int16, geo=None, proj=None):
    # 创建驱动
    driver = gdal.GetDriverByName('GTiff')
    options = ['COMPRESS={}'.format('LZW')]
    # options = ['COMPRESS={}'.format('LZW'), 'BIGTIFF=YES'] # 压缩大于4G的tif用这个
    out_ds = driver.Create(output_path, cols, rows, bands, dtype, options=options)
    if not out_ds:
        raise Exception("无法创建文件：{}".format(output_path))
    # 设置地理变换和投影信息
    if geo:
        out_ds.SetGeoTransform(geo)
    if proj:
        out_ds.SetProjection(proj)
    # 写入每个波段的数据
    nodata_value = 0.0
    if data.ndim == 3:
        # 处理三维数据，多个波段
        for i in range(data.shape[0]):
            band_data = out_ds.GetRasterBand(i + 1)
            band_data.WriteArray(data[i])
            band_data.SetNoDataValue(float(nodata_value))
    elif data.ndim == 2:
        # 处理二维数据，单个波段
        band_data = out_ds.GetRasterBand(1)
        band_data.WriteArray(data)
        band_data.SetNoDataValue(float(nodata_value))
    else:
        raise ValueError("提供的数据类型不正确")
    # 保存并关闭文件
    out_ds.FlushCache()
    out_ds = None


# -------------------------------------------------------------
def identify_adjacent_connections(arr, bias):
    # 定义结构元素
    structure = np.array([[0, 1, 0],
                          [1, 1, 1],
                          [0, 1, 0]])

    # 使用label函数标记连续区域
    labeled_arr, num_features = label(arr != 0, structure=structure)
    labeled_arr[labeled_arr > 0] += bias

    # 保存初始的arr用于映射
    original_arr = arr.copy()

    # 遍历labeled_arr的每一行
    for i in range(labeled_arr.shape[0]):
        # 获取当前行的label值
        label_value = labeled_arr[i, 0]

        # 如果这一行两个值相同且不为0
        if labeled_arr[i, 0] == labeled_arr[i, 1] and label_value != 0:
            # 获取arr中的值
            val_a = arr[i, 0]
            val_b = arr[i, 1]

            # 替换arr中所有val_a的值为label_value
            arr[arr == val_a] = label_value

            # 替换arr中所有val_b的值为label_value
            arr[arr == val_b] = label_value

    # 初始化字典，用于映射更新后的arr值到原始arr的多值
    col1_dict = {}  # 第一列映射
    col2_dict = {}  # 第二列映射

    # 遍历更新后的arr和原始的original_arr，构建映射
    for i in range(arr.shape[0]):
        updated_val_a, updated_val_b = arr[i, 0], arr[i, 1]
        original_val_a, original_val_b = original_arr[i, 0], original_arr[i, 1]

        # 构建第一列映射，忽略0值和相同值的映射
        if updated_val_a != 0 and updated_val_a != original_val_a:
            if updated_val_a in col1_dict:
                if original_val_a not in col1_dict[updated_val_a]:
                    col1_dict[updated_val_a].append(original_val_a)
            else:
                col1_dict[updated_val_a] = [original_val_a]

        # 构建第二列映射，忽略0值和相同值的映射
        if updated_val_b != 0 and updated_val_b != original_val_b:
            if updated_val_b in col2_dict:
                if original_val_b not in col2_dict[updated_val_b]:
                    col2_dict[updated_val_b].append(original_val_b)
            else:
                col2_dict[updated_val_b] = [original_val_b]

    return arr, col1_dict, col2_dict


def replace_array_values(arr, col_dict, chunk_size=1000):
    # 构建反向映射字典，方便快速查找
    reverse_map = {}
    for new_val, old_vals in col_dict.items():
        for old_val in old_vals:
            reverse_map[old_val] = new_val

    # 获取数组中所有唯一值
    unique_vals = np.unique(arr)

    # 创建映射数组，将唯一值替换成新值
    mapped_vals = np.array([reverse_map.get(val, val) for val in tqdm(unique_vals, desc="构建映射表")])

    # 按块处理，避免内存溢出
    def process_chunk(chunk):
        indices = np.searchsorted(unique_vals, chunk)
        return mapped_vals[indices]

    # 创建空数组来存储结果
    result = np.empty_like(arr)

    # 计算总的块数
    num_chunks_row = (arr.shape[1] + chunk_size - 1) // chunk_size
    num_chunks_col = (arr.shape[2] + chunk_size - 1) // chunk_size
    total_chunks = num_chunks_row * num_chunks_col

    # 仅在最外层循环添加 tqdm 进度条
    chunk_count = 0
    for i in tqdm(range(0, arr.shape[1], chunk_size), desc="处理数据", total=num_chunks_row):
        for j in range(0, arr.shape[2], chunk_size):
            # 处理每一块
            result[:, i:i + chunk_size, j:j + chunk_size] = process_chunk(arr[:, i:i + chunk_size, j:j + chunk_size])
            chunk_count += 1

    return result


# -------------------------------------------------------------
@run_time
def identify_patches(arr, bias=0):
    # 定义结构元素
    structure = np.array([[0, 1, 0],
                          [1, 1, 1],
                          [0, 1, 0]])
    # 使用scipy的label函数标记连续区域，包括斜向
    labeled_arr, num = label(arr == 1, structure=structure)
    # 创建一个新数组，用来存储标记值
    labeled_arr[labeled_arr > 0] += bias
    # 输出斑块的数量
    # print("Number of patches:", num)
    return labeled_arr, num


# -------------------------------------------------------------
@run_time
def query_southern_boundary(image, background=0, dtype=np.uint32):
    arr = image[0]  # 假设image是一个元组或列表，第一个元素是二维数组
    rows, cols = arr.shape
    result = np.zeros_like(arr, dtype=dtype)
    # 向量化检查非背景像素
    non_background = arr != background
    for j in tqdm(range(cols), desc="[south]"):
        column_data = non_background[:, j]
        # 检查当前列是否有非背景像素
        if not np.any(column_data):
            continue
        # 从底部向上寻找第一个非背景像素
        valid_idx = np.where(column_data)[0]
        bottom = valid_idx[-1]
        length = 0
        for i in range(bottom, -1, -1):
            if column_data[i]:
                length += 1
                result[i, j] = length
            else:
                length = 0
    # 清理大型对象
    del arr, non_background, column_data, valid_idx
    gc.collect()  # 显式调用垃圾收集
    return result


@run_time
def query_northern_boundary(image, background=0, dtype=np.uint32):
    arr = image[0]  # 假设image是一个元组或列表，第一个元素是二维数组
    rows, cols = arr.shape
    result = np.zeros_like(arr, dtype=dtype)
    # 向量化检查非背景像素
    non_background = arr != background
    for j in tqdm(range(cols), desc="[north]"):
        column_data = non_background[:, j]
        if not np.any(column_data):
            continue
        # 从顶部向下寻找第一个非背景像素
        valid_idx = np.where(column_data)[0]
        top = valid_idx[0]
        length = 0
        for i in range(top, rows):
            if column_data[i]:
                length += 1
                result[i, j] = length
            else:
                length = 0
    del arr, non_background, column_data, valid_idx  # 删除大型对象
    gc.collect()  # 显式调用垃圾收集
    return result


@run_time
def query_western_boundary(image, background=0, dtype=np.uint32):
    arr = image[0]  # 假设image是一个元组或列表，第一个元素是二维数组
    rows, cols = arr.shape
    result = np.zeros_like(arr, dtype=dtype)
    # 向量化检查非背景像素
    non_background = arr != background
    for i in tqdm(range(rows), desc="[west]"):
        row_data = non_background[i, :]
        # 检查当前行是否有非背景像素
        if not np.any(row_data):
            continue
        # 从左向右寻找第一个非背景像素
        valid_idx = np.where(row_data)[0]
        left = valid_idx[0]
        length = 0
        for j in range(left, cols):
            if row_data[j]:
                length += 1
                result[i, j] = length
            else:
                length = 0
    # 清理大型对象
    del arr, non_background, row_data, valid_idx
    gc.collect()  # 显式调用垃圾收集
    return result


@run_time
def query_eastern_boundary(image, background=0, dtype=np.uint32):
    arr = image[0]  # 假设image是一个元组或列表，第一个元素是二维数组
    rows, cols = arr.shape
    result = np.zeros_like(arr, dtype=dtype)
    # 向量化检查非背景像素
    non_background = arr != background
    for i in tqdm(range(rows), desc="[east]"):
        row_data = non_background[i, :]
        # 检查当前行是否有非背景像素
        if not np.any(row_data):
            continue
        # 从右向左寻找第一个非背景像素
        valid_idx = np.where(row_data)[0]
        right = valid_idx[-1]
        length = 0
        for j in range(right, -1, -1):
            if row_data[j]:
                length += 1
                result[i, j] = length
            else:
                length = 0
    # 清理大型对象
    del arr, non_background, row_data, valid_idx
    gc.collect()  # 显式调用垃圾收集
    return result
