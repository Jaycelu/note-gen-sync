# Linux 磁盘管理实践：挂载和扩展 LVM 逻辑卷

## 1. 实践背景

本次实践的目标是利用两块新安装的 2TB 固态硬盘（SSD），将其全部可用空间挂载到 Linux 系统中。其中一块磁盘 (`/dev/nvme0n1`) 将作为独立的数据盘，另一块 (`/dev/nvme1n1`) 则用于扩展已有的根目录 (`/`)。

## 2. 初始磁盘状态

在开始操作前，通过以下命令查看了系统中的磁盘和文件系统情况。

* **`df -h`**: 显示已挂载文件系统的使用情况。
  * 此时，`df -h` 尚未显示两块 2TB 磁盘的大部分空间，因为它们还未被挂载。
  * 根目录 `/` (`/dev/mapper/ubuntu--vg-ubuntu--lv`) 仅有 98GB，显示为 100% 使用率。
* **`lsblk` / `fdisk -l`**: 显示了所有块设备及其分区。
  * `/dev/nvme0n1`: 拥有一个 1.8T 的分区 (`/dev/nvme0n1p3`)，但未被挂载。
  * `/dev/nvme1n1`: 拥有一个 1.8T 的分区 (`/dev/nvme1n1p3`)，该分区已被用作 **LVM 物理卷**，但大部分空间尚未分配。

## 3. 磁盘挂载与分区步骤

### 3.1. 挂载独立数据盘 (`/dev/nvme0n1p3`)

这块磁盘将作为一个全新的、独立的分区，挂载到 `/data` 目录下。

1. 格式化分区：
   将 /dev/nvme0n1p3 分区格式化为 ext4 文件系统。

   ```
   sudo mkfs.ext4 /dev/nvme0n1p3
   ```

   **注意：** 此操作会擦除该分区上的所有数据。
2. 创建挂载点：
   在根目录下创建一个名为 data 的目录，作为新分区的挂载点。

   ```
   sudo mkdir /data
   ```
3. 临时挂载：
   立即将 /dev/nvme0n1p3 挂载到 /data 目录。

   ```
   sudo mount /dev/nvme0n1p3 /data
   ```

   此时，运行 `df -h` 即可看到 `/data` 目录已成功挂载，并显示其 1.8T 的空间。
4. 设置开机自动挂载：
   为了让挂载在系统重启后依然有效，需要编辑 /etc/fstab 文件。

   * 首先，使用 `blkid` 命令获取分区的 UUID（一个唯一的标识符）。

     ```
     sudo blkid /dev/nvme0n1p3
     ```
   * 然后，用 `nano` 编辑器打开 `/etc/fstab` 文件，并在文件末尾添加一行配置。

     ```
     sudo nano /etc/fstab
     ```

     在文件末尾添加以下内容，确保替换为实际的 UUID：

     ```
     UUID=efc6f7bb-a584-4dc2-82ff-16acd4692798 /data ext4 defaults 0 2
     ```

     保存并退出（`Ctrl+O`，`Enter`，`Ctrl+X`）。

### 3.2. 扩展 LVM 逻辑卷（`ubuntu--vg-ubuntu--lv`）

这块磁盘的 1.8T 分区 (`/dev/nvme1n1p3`) 已经被用作 LVM (逻辑卷管理)。为了使用剩余空间，需要通过 LVM 命令来扩展。

1. 检查 LVM 状态：
   通过 pvs 和 vgs 命令确认卷组 (VG) 中可用的空闲空间。

   ```
   sudo pvs
   sudo vgs
   ```

   输出显示 `ubuntu-vg` 卷组中有约 1.72T 的空闲空间 (`VFree`)。
2. 扩展逻辑卷：
   使用 lvextend 命令将 ubuntu-vg 卷组中所有剩余的空闲空间 (+100%FREE) 分配给根目录所在的逻辑卷 (ubuntu--lv)。

   ```
   sudo lvextend -l +100%FREE /dev/mapper/ubuntu--vg-ubuntu--lv
   ```
3. 调整文件系统大小：
   扩展逻辑卷后，文件系统本身的大小并未改变。需要使用 resize2fs 命令来调整文件系统，使其占用新分配的空间。

   ```
   sudo resize2fs /dev/mapper/ubuntu--vg-ubuntu--lv
   ```

## 4. 最终结果

完成所有步骤后，再次运行 `df -h`，可以看到两块 2TB 磁盘的空间已全部被利用：

```
root@dy:~# df -h
Filesystem                               Size  Used Avail Use% Mounted on
...
/dev/mapper/ubuntu--vg-ubuntu--lv      1.8T   94G  1.7T   6% /
...
/dev/nvme0n1p3                         1.8T   28K  1.7T   1% /data
...
```

* **根目录 `/`** 的大小已从 98GB **扩展至 1.8T**。
* **`/data`** 目录已成功挂载了另一块 **1.8T** 的独立磁盘空间。

这次实践成功地将两块物理磁盘的空间，通过不同的方式（标准分区挂载和 LVM 扩展），有效地整合到了系统中。
