import cv2
import time
import numpy as np
import serial

# ==================================================
# 串口配置
# ==================================================
COM_PORT = "COM12"    # 请务必修改为你开发板在电脑上识别出的端口
BAUD_RATE = 115200   # 极速波特率，若画面花屏可降级为 115200

# ==================================================
# 图像配置 (保持 64x64)
# ==================================================
FACE_W = 64
FACE_H = 64

def bgr_to_rgb565_bytes(img_bgr):
    """
    OpenCV (BGR) -> RGB565 (高位在前，低位在后) -> 纯二进制 bytes
    """
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    r = img_rgb[:, :, 0].astype(np.uint16)
    g = img_rgb[:, :, 1].astype(np.uint16)
    b = img_rgb[:, :, 2].astype(np.uint16)

    rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    high = (rgb565 >> 8).astype(np.uint8)
    low = (rgb565 & 0xFF).astype(np.uint8)

    out = np.empty((img_rgb.shape[0], img_rgb.shape[1], 2), dtype=np.uint8)
    out[:, :, 0] = high
    out[:, :, 1] = low
    return out.tobytes()

def crop_face_or_center(frame, faces):
    h, w = frame.shape[:2]
    if len(faces) > 0:
        x, y, fw, fh = faces[0]
        cx, cy = x + fw // 2, y + fh // 2
        size = int(max(fw, fh) * 1.4)
        x1, y1 = max(0, cx - size // 2), max(0, cy - size // 2)
        x2, y2 = min(w, cx + size // 2), min(h, cy + size // 2)
        return frame[y1:y2, x1:x2]
    else:
        size = min(w, h)
        x1, y1 = (w - size) // 2, (h - size) // 2
        return frame[y1:y1 + size, x1:x1 + size]

def main():
    print(f"打开串口 {COM_PORT} (波特率 {BAUD_RATE})...")
    
    # ---------------- 关键修改 1：手动配置串口，防止单片机重启 ----------------
    try:
        ser = serial.Serial()
        ser.port = COM_PORT
        ser.baudrate = BAUD_RATE
        ser.timeout = 1
        ser.setDTR(False)  # 关掉 DTR 信号，防止复位开发板
        ser.setRTS(False)  # 关掉 RTS 信号
        ser.open()
    except Exception as e:
        print(f"串口打开失败: {e}")
        return
    # ------------------------------------------------------------------------

    cap = cv2.VideoCapture(0)
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

    print("开始串口推流... (按 ESC 退出)")
    
    sync_header = bytes([0x5A, 0xA5, 0xAA, 0x55])

    while True:
        ret, frame = cap.read()
        if not ret: break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))

        preview = frame.copy()
        for x, y, w, h in faces:
            cv2.rectangle(preview, (x, y), (x + w, y + h), (0, 255, 0), 2)
        cv2.imshow("camera preview", preview)

        face_img = crop_face_or_center(frame, faces)
        face_img = cv2.resize(face_img, (FACE_W, FACE_H))
        img_bytes = bgr_to_rgb565_bytes(face_img)

        payload = sync_header + img_bytes
        ser.write(payload)

        # ---------------- 关键修改 2：尊重物理规律，延时必须大于 0.18秒 ----------------
        # 0.2 秒相当于 5 FPS，这是 460800 波特率下最安全的稳定帧率
        time.sleep(0.2) 
        # -----------------------------------------------------------------------------

        if cv2.waitKey(1) == 27:
            break

    cap.release()
    cv2.destroyAllWindows()
    ser.close()

if __name__ == "__main__":
    main()