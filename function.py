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
    "Read tif data, columns, rows, bands, formats, transforms, projections"
    in_ds = gdal.Open(tiff_path, gdal.GA_ReadOnly)
    if not in_ds:
        raise FileNotFoundError(f"Unable to open file：{tiff_path}")
    try:
        cols, rows, bands = in_ds.RasterXSize, in_ds.RasterYSize, in_ds.RasterCount
        dtype = in_ds.GetRasterBand(1).DataType
        data_type_name = gdal.GetDataTypeName(dtype)
        print(f"Driver: {in_ds.GetDriver().ShortName}")
        print(f"Height (row): {rows}")
        print(f"Width (column): {cols}")
        print(f"Bands: {bands}")
        print(f"Data type: {data_type_name}")
        geo = in_ds.GetGeoTransform()
        proj = in_ds.GetProjection()
        if geo:
            print(f"Geographical transformation：{geo}")
            print(f"-Top-left coordinate: ({geo[0]}, {geo[3]})")
            print(f"-Pixel width: {geo[1]}")
            print(f"-Pixel height: {geo[5]}")
        if proj:
            print(f"Projection information: {proj}")
        data = in_ds.ReadAsArray()
        if data.ndim == 2:
            data = np.expand_dims(data, axis=0)
    finally:
        in_ds = None
    return data, cols, rows, bands, dtype, geo, proj


@run_time
def sliding_clipping_diy(input_path, output_folder, clip_width, clip_height):
    '''This function supports custom rectangle clipping'''
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    in_ds = gdal.Open(input_path)
    filename = os.path.splitext(os.path.basename(input_path))[0]
    # Calculate the number of cuts in landscape and portrait
    num_cols = in_ds.RasterXSize // clip_width
    num_rows = in_ds.RasterYSize // clip_height
    print('num_rows=%d,num_cols=%d' % (num_rows, num_cols))
    geo = in_ds.GetGeoTransform()
    proj = in_ds.GetProjection()
    # Loop crop image
    for x in range(num_cols):
        for y in range(num_rows):
            # Calculates the start and end positions of the current clipped window
            xoff = x * clip_width
            yoff = y * clip_height
            # Read the data of the current window
            bands_data = []
            bands = in_ds.RasterCount
            # Loop through all bands
            for i in range(1, bands + 1):
                band_data = in_ds.GetRasterBand(i).ReadAsArray(xoff, yoff, clip_width, clip_height)
                bands_data.append(band_data)
            # Build output file name
            out_file = os.path.join(output_folder, f'{filename}_{x}_{y}.tif')
            # Create the cropped image file and set the spatial reference and affine transformation parameters
            driver = gdal.GetDriverByName('GTiff')
            options = ['COMPRESS={}'.format('LZW')]
            # options = ['COMPRESS={}'.format('LZW'), 'BIGTIFF=YES'] # # Compress tif larger than 4G with this
            out_dataset = driver.Create(out_file, clip_width, clip_height, bands, in_ds.GetRasterBand(1).DataType,
                                        options=options)
            out_dataset.SetGeoTransform(
                (geo[0] + xoff * geo[1], geo[1], 0, geo[3] + yoff * geo[5], 0, geo[5]))
            out_dataset.SetProjection(proj)
            # # Write output image data
            for i, band_data in enumerate(bands_data, start=1):
                out_dataset.GetRasterBand(i).WriteArray(band_data)
            out_dataset.FlushCache()
            out_dataset = None


def write(output_path, data, cols, rows, bands=1, dtype=gdal.GDT_Int16, geo=None, proj=None):
    driver = gdal.GetDriverByName('GTiff')
    options = ['COMPRESS={}'.format('LZW')]
    # options = ['COMPRESS={}'.format('LZW'), 'BIGTIFF=YES']
    out_ds = driver.Create(output_path, cols, rows, bands, dtype, options=options)
    if not out_ds:
        raise Exception("Unable to create file：{}".format(output_path))
    if geo:
        out_ds.SetGeoTransform(geo)
    if proj:
        out_ds.SetProjection(proj)
    nodata_value = 0.0
    if data.ndim == 3:
        for i in range(data.shape[0]):
            band_data = out_ds.GetRasterBand(i + 1)
            band_data.WriteArray(data[i])
            band_data.SetNoDataValue(float(nodata_value))
    elif data.ndim == 2:
        band_data = out_ds.GetRasterBand(1)
        band_data.WriteArray(data)
        band_data.SetNoDataValue(float(nodata_value))
    else:
        raise ValueError("The data type provided is incorrect")
    out_ds.FlushCache()
    out_ds = None


# -------------------------------------------------------------
def identify_adjacent_connections(arr, bias):
    # Define structure element
    structure = np.array([[0, 1, 0],
                          [1, 1, 1],
                          [0, 1, 0]])

    # Use the label function to mark contiguous areas
    labeled_arr, num_features = label(arr != 0, structure=structure)
    labeled_arr[labeled_arr > 0] += bias

    # Save the original arr for mapping
    original_arr = arr.copy()

    # Walk through each row of labeled_arr
    for i in range(labeled_arr.shape[0]):
        # Gets the label value of the current row
        label_value = labeled_arr[i, 0]

        # If the two values in this row are the same and not 0
        if labeled_arr[i, 0] == labeled_arr[i, 1] and label_value != 0:
            val_a = arr[i, 0]
            val_b = arr[i, 1]
            arr[arr == val_a] = label_value
            arr[arr == val_b] = label_value

    # Initializes a dictionary that maps updated arr values to multiple values of the original arr
    col1_dict = {}
    col2_dict = {}

    # Iterate over the updated arr and the original original_arr to build the mapping
    for i in range(arr.shape[0]):
        updated_val_a, updated_val_b = arr[i, 0], arr[i, 1]
        original_val_a, original_val_b = original_arr[i, 0], original_arr[i, 1]

        # Build the first column map, ignoring 0 values and mappings of the same value
        if updated_val_a != 0 and updated_val_a != original_val_a:
            if updated_val_a in col1_dict:
                if original_val_a not in col1_dict[updated_val_a]:
                    col1_dict[updated_val_a].append(original_val_a)
            else:
                col1_dict[updated_val_a] = [original_val_a]

        # Build a second column map, ignoring 0 values and mappings of the same value
        if updated_val_b != 0 and updated_val_b != original_val_b:
            if updated_val_b in col2_dict:
                if original_val_b not in col2_dict[updated_val_b]:
                    col2_dict[updated_val_b].append(original_val_b)
            else:
                col2_dict[updated_val_b] = [original_val_b]

    return arr, col1_dict, col2_dict


def replace_array_values(arr, col_dict, chunk_size=1000):
    # Build a reverse mapping dictionary for quick lookup
    reverse_map = {}
    for new_val, old_vals in col_dict.items():
        for old_val in old_vals:
            reverse_map[old_val] = new_val

    # Gets all unique values in the array
    unique_vals = np.unique(arr)

    # Creates a mapped array, replacing unique values with new values
    mapped_vals = np.array([reverse_map.get(val, val) for val in tqdm(unique_vals, desc="构建映射表")])

    # Block processing to avoid memory overflow
    def process_chunk(chunk):
        indices = np.searchsorted(unique_vals, chunk)
        return mapped_vals[indices]

    # Create an empty array to store the results
    result = np.empty_like(arr)

    # Calculate the total number of blocks
    num_chunks_row = (arr.shape[1] + chunk_size - 1) // chunk_size
    num_chunks_col = (arr.shape[2] + chunk_size - 1) // chunk_size
    total_chunks = num_chunks_row * num_chunks_col

    chunk_count = 0
    for i in tqdm(range(0, arr.shape[1], chunk_size), desc="Processing data", total=num_chunks_row):
        for j in range(0, arr.shape[2], chunk_size):
            result[:, i:i + chunk_size, j:j + chunk_size] = process_chunk(arr[:, i:i + chunk_size, j:j + chunk_size])
            chunk_count += 1

    return result


# -------------------------------------------------------------
@run_time
def identify_patches(arr, bias=0):
    structure = np.array([[0, 1, 0],
                          [1, 1, 1],
                          [0, 1, 0]])
    labeled_arr, num = label(arr == 1, structure=structure)
    labeled_arr[labeled_arr > 0] += bias
    # print("Number of patches:", num)
    return labeled_arr, num


# -------------------------------------------------------------
@run_time
def query_southern_boundary(image, background=0, dtype=np.uint32):
    arr = image[0]
    rows, cols = arr.shape
    result = np.zeros_like(arr, dtype=dtype)
    # Vectorization checks non-background pixels
    non_background = arr != background
    for j in tqdm(range(cols), desc="[south]"):
        column_data = non_background[:, j]
        # Check whether the current column has non-background pixels
        if not np.any(column_data):
            continue
        # Find the first non-background pixel from the bottom up
        valid_idx = np.where(column_data)[0]
        bottom = valid_idx[-1]
        length = 0
        for i in range(bottom, -1, -1):
            if column_data[i]:
                length += 1
                result[i, j] = length
            else:
                length = 0
    # Cleaning large objects
    del arr, non_background, column_data, valid_idx
    gc.collect()  # Invoke garbage collection explicitly
    return result


@run_time
def query_northern_boundary(image, background=0, dtype=np.uint32):
    arr = image[0]
    rows, cols = arr.shape
    result = np.zeros_like(arr, dtype=dtype)
    non_background = arr != background
    for j in tqdm(range(cols), desc="[north]"):
        column_data = non_background[:, j]
        if not np.any(column_data):
            continue
        valid_idx = np.where(column_data)[0]
        top = valid_idx[0]
        length = 0
        for i in range(top, rows):
            if column_data[i]:
                length += 1
                result[i, j] = length
            else:
                length = 0
    del arr, non_background, column_data, valid_idx
    gc.collect()
    return result


@run_time
def query_western_boundary(image, background=0, dtype=np.uint32):
    arr = image[0]
    rows, cols = arr.shape
    result = np.zeros_like(arr, dtype=dtype)
    non_background = arr != background
    for i in tqdm(range(rows), desc="[west]"):
        row_data = non_background[i, :]
        if not np.any(row_data):
            continue
        valid_idx = np.where(row_data)[0]
        left = valid_idx[0]
        length = 0
        for j in range(left, cols):
            if row_data[j]:
                length += 1
                result[i, j] = length
            else:
                length = 0
    del arr, non_background, row_data, valid_idx
    gc.collect()
    return result


@run_time
def query_eastern_boundary(image, background=0, dtype=np.uint32):
    arr = image[0]
    rows, cols = arr.shape
    result = np.zeros_like(arr, dtype=dtype)
    non_background = arr != background
    for i in tqdm(range(rows), desc="[east]"):
        row_data = non_background[i, :]
        if not np.any(row_data):
            continue
        valid_idx = np.where(row_data)[0]
        right = valid_idx[-1]
        length = 0
        for j in range(right, -1, -1):
            if row_data[j]:
                length += 1
                result[i, j] = length
            else:
                length = 0
    del arr, non_background, row_data, valid_idx
    gc.collect()
    return result
