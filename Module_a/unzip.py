import os
import zipfile
import rarfile
import py7zr
rarfile.UNRAR_TOOL = r"C:\Program Files\WinRAR\UnRAR.exe"
def extract_file(file_path, target_path):
    os.makedirs(target_path, exist_ok=True)

    if file_path.lower().endswith(".zip"):
        with zipfile.ZipFile(file_path, 'r') as zf:
            for info in zf.infolist():
                filename = info.filename
                # 嘗試不同編碼還原檔名
                try:
                    filename = filename.encode("cp437").decode("utf-8")
                except:
                    try:
                        filename = filename.encode("cp437").decode("big5")
                    except:
                        try:
                            filename = filename.encode("cp437").decode("gbk")
                        except:
                            pass  # 保持原樣
                extracted_path = os.path.join(target_path, filename)
                os.makedirs(os.path.dirname(extracted_path), exist_ok=True)
                with zf.open(info) as source, open(extracted_path, "wb") as target:
                    target.write(source.read())
    elif file_path.lower().endswith(".rar"):
        with rarfile.RarFile(file_path, 'r') as rf:
            rf.extractall(target_path)
    elif file_path.lower().endswith(".7z"):
        with py7zr.SevenZipFile(file_path, mode='r') as sz:
            sz.extractall(path=target_path)
def extract_archive(src_file: str, dst_folder: str):
    """
    解壓縮單一檔案到指定資料夾
    :param src_file: 壓縮檔路徑 (.zip / .rar / .7z)
    :param dst_folder: 解壓縮目標資料夾
    """
    os.makedirs(dst_folder, exist_ok=True)
    extensions = (".zip", ".rar", ".7z")

    if not src_file.lower().endswith(extensions):
        raise ValueError(f"不支援的壓縮檔格式: {src_file}")

    print(f"解壓縮 {src_file} -> {dst_folder}")
    try:
        extract_file(src_file, dst_folder) 
    except Exception as e:
        print(f"解壓縮失敗: {src_file}, 錯誤: {e}")

if __name__ == "__main__":
    source = r"D:\coding\ownDCio\2025FallEvent\File responses.rar"
    dest   = r"D:\coding\ownDCio\2025FallEvent\pieces"
    extract_archive(source, dest)
