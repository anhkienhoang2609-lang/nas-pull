# NAS Pull

App GUI để tìm và kéo file từ NAS (network share) về máy local theo danh sách tên file/ID.

## Môi trường

- Linux (Ubuntu)
- Python 3.10+
- NAS mount qua CIFS (`/mnt/footage_pool`, v.v.)

## Cài đặt

```bash
pip install customtkinter
```

## Cấu hình (`this.json`)

Copy file mẫu rồi sửa lại:

```bash
cp this.json.example this.json
```

Nội dung cần thiết:

```json
{
    "GlobalSettings": {
        "nas_path": "/mnt/footage_pool",
        "export_path": "/home/user/Downloads"
    }
}
```

> **Lưu ý `nas_path`:** Chỉ để các NAS có số lượng file vừa phải (<500k file). NAS quá lớn (1M+ file) sẽ làm quét rất lâu. Nhiều NAS thì ngăn cách bằng dấu phẩy: `/mnt/nas1, /mnt/nas2`.

## Chạy app

```bash
python3 nas_ui.py
```

Hoặc dùng shortcut desktop (`NasPull.desktop`).

## Build thành file thực thi (PyInstaller)

```bash
pip install pyinstaller
pyinstaller nas_ui.spec
# Output: dist/nas_ui
```

## Cách dùng

1. **Nhập danh sách file** vào ô trên — mỗi dòng một file, định dạng:
   ```
   Tên file đích | file_id_trên_NAS
   ```
   Ví dụ:
   ```
   Vietnam Travel 4K | vietnam-travel-4k_preview
   Hanoi Street Food  | hanoi_street_food_hd
   ```

2. **Chọn Folder đích** — nơi file sẽ được kéo về

3. **Refresh Cache** (lần đầu hoặc khi NAS có file mới) — quét toàn bộ NAS và lưu index vào `nas_cache.json`. Chỉ cần làm 1 lần, lần sau load tức thì.

4. **PULL FROM NAS** — tìm từng file trong index và copy về folder đích

## Cơ chế hoạt động

```
NAS paths → find -type f → index {tên_file: đường_dẫn} → lưu cache
Khi pull: tra index theo ID → cp file về folder đích
```

- Cache lưu tại `nas_cache.json` (bị gitignore)
- Nếu NAS path thay đổi → cache tự động bị bỏ qua, quét lại
- Quét song song nhiều NAS path bằng `ThreadPoolExecutor`
- Live progress log mỗi 5,000 file để thấy tiến trình

## Lịch sử vấn đề & fix

| Ngày | Vấn đề | Fix |
|------|--------|-----|
| 2026-06-29 | App quét NAS mãi không thấy chạy, trông như bị đứng | Thêm live counter mỗi 5,000 file trong log |
| 2026-06-29 | Quét 2 NAS tuần tự quá chậm (footage_pool 30s + project_tripinsigh_03 3+ phút) | Đổi sang quét song song bằng `ThreadPoolExecutor` |
| 2026-06-29 | `project_tripinsigh_03` có 1M+ file, quét không bao giờ xong | Bỏ khỏi `nas_path` trong `this.json`, chỉ dùng `footage_pool` |

## File quan trọng

```
nas_ui.py          ← toàn bộ logic app (1 file duy nhất)
nas_ui.spec        ← PyInstaller build config
this.json          ← config (KHÔNG commit — có trong .gitignore)
this.json.example  ← mẫu config không có thông tin nhạy cảm
nas_cache.json     ← cache index NAS (auto-generated, KHÔNG commit)
```

## Môi trường production

- Machine: Linux Ubuntu, user `mava`
- NAS IP: `192.168.1.111` (CIFS mount)
- NAS đang dùng: `/mnt/footage_pool` (~330k file)
- Desktop shortcut: `/home/mava/Desktop/NasPull.desktop`
- Source: `/home/mava/Mavamixi/nas_ui.py`
