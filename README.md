# Forest patch treatment


## **Overview**  
This project relies on specific libraries and tools. 
To ensure smooth execution of the code, it is recommended to use **Anaconda** for environment management.
Below is a detailed list of dependencies along with installation commands, 
suitable for beginners or users unfamiliar with environment setup.

---

## **Dependencies**  

The following Python libraries are required for this project, 
with recommended stable versions listed. 
You may also use the latest versions if compatible.

| **Library** | **Version** | **Installation Command** |
|------------|------------|-------------------------|
| Python     | 3.9        | Installed by default when creating the Conda environment |
| NumPy      | 1.21.5     | `conda install numpy=1.21.5` |
| SciPy      | 1.7.3      | `conda install scipy=1.7.3` |
| TQDM       | 4.64.1     | `conda install tqdm=4.64.1` |
| GDAL       | 3.4.0      | `conda install -c conda-forge gdal=3.4.0` |

---

## **How to use**

Processing large-scale forest patches requires substantial computation time.
To simplify algorithm testing, 
we have prepared a **demo dataset**, a small-sized forest patch file `test_tif/forest_test.tif`.
You can run `main.py` to quickly test the algorithm and generate result files, 
which can be opened and examined using GIS software.
All output files are stored in the `test_tif` directory. Specifically, 
***Method 1*** generates four result files `test_tif/*.tif`, as shown in *Figure 1*, 
while ***Method 2*** produces two result files `test_tif/clip/*_PR.tif`, as shown in *Figure 3*.

---
## **Demo**
### **Method 1: Four-Directional Forest Boundary Detection**
This algorithm is designed for forest gradient queries using binary images of forest distribution. It calculates the distance of each forest pixel to the nearest border in four fundamental directions: east, south, west, and north. 
By processing images in these four directions, the algorithm determines the proximity of each forest pixel to the nearest edge in its respective direction, enabling a comprehensive quantitative analysis of forest edge features.

Moreover, this method overcomes the computational redundancy caused by traditional complex algorithms for locating forest edges and internal gradient positions. 
It allows users to efficiently query the distance to the nearest edge in a specific direction or identify the minimum edge-to-internal gradient distance among the four directions, 
facilitating ecological process-related studies.  

![img/img1.jpg](img/img1.jpg)
***Figure 1: Computation Results of Method 1***  

### **Method 2: Distributed fragment connectivity identification (DFCI)**
The Distributed Fragment Connectivity Identification (DFCI) algorithm is designed to efficiently identify and analyze forest patches across large, 
highly fragmented regions, such as Africa. In these landscapes, 
fragmentation results in numerous isolated forest patches of varying sizes, 
making large-scale processing computationally demanding. Due to memory constraints, 
directly processing binary forest maps in a single operation is infeasible. 
To overcome this challenge, DFCI employs a distributed computing approach to systematically identify and connect forest fragments. 
This algorithm enables scalable and efficient analysis of forest connectivity, 
facilitating better assessment of fragmentation patterns and ecological connectivity.

![img/img2.jpg](img/img2.jpg)
***Figure 2: Conceptual Diagram of the DFCI Algorithm***  


![img/img3.jpg](img/img3.jpg)
***Figure 3: Computation Results of the DFCI Algorithm***


---
## License
Certain implementations within this repository are currently patent-pending.  
Use of this code must comply with the patent clause of the **Apache 2.0 License**.
