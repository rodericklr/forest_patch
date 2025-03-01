from function import *


def traverse_four_directions(input_path):
    # 获取输入文件的目录和文件名
    dir_name, file_name = os.path.split(input_path)

    # 生成四个方向的文件名
    west_path = os.path.join(dir_name, file_name.replace(".tif", "_west.tif"))
    east_path = os.path.join(dir_name, file_name.replace(".tif", "_east.tif"))
    north_path = os.path.join(dir_name, file_name.replace(".tif", "_north.tif"))
    south_path = os.path.join(dir_name, file_name.replace(".tif", "_south.tif"))

    # ——————方向遍历——————
    data, cols, rows, _, _, geo, proj = read(input_path)

    result = None
    result = query_eastern_boundary(data, background=0)
    write(east_path, result, cols, rows, geo=geo, proj=proj)

    result = None
    result = query_western_boundary(data, background=0)
    write(west_path, result, cols, rows, geo=geo, proj=proj)

    result = None
    result = query_northern_boundary(data, background=0)
    write(north_path, result, cols, rows, geo=geo, proj=proj)

    result = None
    result = query_southern_boundary(data, background=0)
    write(south_path, result, cols, rows, geo=geo, proj=proj)


def identify_isolated_patches(input_path):
    # 创建 clip 目录
    clip_dir = os.path.join(os.path.dirname(input_path), 'clip')
    os.makedirs(clip_dir, exist_ok=True)  # 如果文件夹不存在则创建
    filename = os.path.splitext(os.path.basename(input_path))[0]  # 提取文件名（不含扩展名）

    path_clp1 = os.path.join(clip_dir, f"{filename}_0_0.tif")
    path_clp2 = os.path.join(clip_dir, f"{filename}_1_0.tif")

    path_clp1_P = os.path.join(clip_dir, f"{filename}_0_0_P.tif")
    path_clp2_P = os.path.join(clip_dir, f"{filename}_1_0_P.tif")

    path_clp1_PR = os.path.join(clip_dir, f"{filename}_0_0_PR.tif")
    path_clp2_PR = os.path.join(clip_dir, f"{filename}_1_0_PR.tif")

    path_arr1 = os.path.join(clip_dir, "arr1_edge.npy")
    path_arr2 = os.path.join(clip_dir, "arr2_edge.npy")

    # Step_1: 裁剪为图1和图2
    _, cols, rows, _, _, _, _ = read(input_path)
    sliding_clipping_diy(input_path, clip_dir, int(cols / 2), rows)  # 裁剪成左右两张

    # Step_2: 获取图1最后一列
    arr1, cols1, rows1, bands1, dtype1, geo1, proj1 = read(path_clp1)
    arr1, num1 = identify_patches(arr1[0], bias=0)
    write(path_clp1_P, arr1, cols1, rows1, 1, gdal.GDT_UInt32, geo=geo1, proj=proj1)
    arr1 = arr1[:, -1]
    np.save(path_arr1, arr1)

    # Step_3: 获取图2第一列
    arr2, cols2, rows2, bands2, dtype2, geo2, proj2 = read(path_clp2)
    arr2, num2 = identify_patches(arr2[0], bias=num1)
    write(path_clp2_P, arr2, cols2, rows2, 1, gdal.GDT_UInt32, geo=geo2, proj=proj2)
    arr2 = arr2[:, 0]
    np.save(path_arr2, arr2)

    # Step_4: 将两列合并成n*2的numpy数组,替换图1
    arr1 = np.load(path_arr1)
    arr2 = np.load(path_arr2)
    arr = np.column_stack((arr1, arr2))
    _, col1_dict, col2_dict = identify_adjacent_connections(arr, bias=num1 + num2)

    arr1, cols1, rows1, bands1, dtype1, geo1, proj1 = read(path_clp1_P)
    arr1 = replace_array_values(arr1, col1_dict)
    write(path_clp1_PR, arr1, cols1, rows1, 1, gdal.GDT_UInt32, geo=geo1, proj=proj1)

    # Step_5: 将两列合并成n*2的numpy数组,替换图2
    arr1 = np.load(path_arr1)
    arr2 = np.load(path_arr2)
    arr = np.column_stack((arr1, arr2))
    _, col1_dict, col2_dict = identify_adjacent_connections(arr, bias=num1 + num2)

    arr2, cols2, rows2, bands2, dtype2, geo2, proj2 = read(path_clp2_P)
    arr2 = replace_array_values(arr2, col2_dict)
    write(path_clp2_PR, arr2, cols2, rows2, 1, gdal.GDT_UInt32, geo=geo2, proj=proj2)


# main program
def main():
    # input tif path
    input_path = r"test_tif\forest_test.tif"
    traverse_four_directions(input_path)
    identify_isolated_patches(input_path)


if __name__ == '__main__':
    main()
