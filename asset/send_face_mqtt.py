import cv2
import time
import numpy as np
import paho.mqtt.client as mqtt

# ==================================================
# MQTT 配置
# Mosquitto Broker 所在电脑的 IP
# ==================================================
BROKER_IP = "192.168.181.57"
BROKER_PORT = 1883

# 开发板订阅这个主题
TOPIC_FACE_CHUNK = "puzhong103/face/chunk"

# ==================================================
# 图像配置
# 提升到 64x64
# ==================================================
FACE_W = 64
FACE_H = 64

# 每包发送 256 个原始图像字节
# 64x64x2 = 8192 字节
# 8192 / 256 = 32 包
CHUNK_SIZE = 256

# 降低单包延迟，加快发送速度
CHUNK_DELAY = 0.1

# 每 8 秒发送一帧
FRAME_INTERVAL = 8.0


def bgr_to_rgb565_bytes(img_bgr):
    """
    OpenCV 读取到的是 BGR888。
    TFTLCD 常用 RGB565。
    这里转换成 RGB565 字节流，高字节在前，低字节在后。
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
    """
    如果检测到人脸，就裁剪人脸区域；
    如果没有检测到人脸，就裁剪画面中心区域。
    """
    h, w = frame.shape[:2]

    if len(faces) > 0:
        x, y, fw, fh = faces[0]

        cx = x + fw // 2
        cy = y + fh // 2
        size = int(max(fw, fh) * 1.4)

        x1 = max(0, cx - size // 2)
        y1 = max(0, cy - size // 2)
        x2 = min(w, cx + size // 2)
        y2 = min(h, cy + size // 2)

        return frame[y1:y2, x1:x2]
    else:
        size = min(w, h)
        x1 = (w - size) // 2
        y1 = (h - size) // 2

        return frame[y1:y1 + size, x1:x1 + size]


def send_frame(client, frame_id, img_bytes):
    """
    把一帧图像分成多包发送。

    Payload 格式：
    F:frame_id:packet_id:total:hexdata
    """
    total = (len(img_bytes) + CHUNK_SIZE - 1) // CHUNK_SIZE

    print(f"\nStart send frame={frame_id}, total packets={total}")

    for packet_id in range(total):
        start = packet_id * CHUNK_SIZE
        end = start + CHUNK_SIZE
        chunk = img_bytes[start:end]

        hex_data = chunk.hex().upper()

        payload = f"F:{frame_id}:{packet_id}:{total}:{hex_data}"

        client.publish(TOPIC_FACE_CHUNK, payload, qos=0, retain=False)

        # 只打印第一包和最后一包，避免终端刷屏
        if packet_id == 0 or packet_id == total - 1:
            print(
                f"send frame={frame_id}, "
                f"packet={packet_id + 1}/{total}, "
                f"bytes={len(chunk)}"
            )

        time.sleep(CHUNK_DELAY)

    print(f"Frame {frame_id} send finished")


def main():
    print("Connecting MQTT broker...")
    print("Broker IP:", BROKER_IP)

    client = mqtt.Client()
    client.connect(BROKER_IP, BROKER_PORT, 60)
    client.loop_start()

    print("MQTT connected")

    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("摄像头打开失败")
        client.loop_stop()
        client.disconnect()
        return

    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )

    frame_id = 0
    last_send_time = 0

    print("开始采集摄像头并通过 MQTT 发送人脸图像")
    print("按 ESC 退出")

    while True:
        ret, frame = cap.read()

        if not ret:
            print("读取摄像头失败")
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        faces = face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(60, 60)
        )

        preview = frame.copy()

        for x, y, w, h in faces:
            cv2.rectangle(
                preview,
                (x, y),
                (x + w, y + h),
                (0, 255, 0),
                2
            )

        cv2.imshow("camera preview", preview)

        now = time.time()

        if now - last_send_time >= FRAME_INTERVAL:
            face_img = crop_face_or_center(frame, faces)

            face_img = cv2.resize(face_img, (FACE_W, FACE_H))

            img_bytes = bgr_to_rgb565_bytes(face_img)

            print("one frame size:", len(img_bytes), "bytes")

            send_frame(client, frame_id, img_bytes)

            frame_id = (frame_id + 1) % 65535

            # 从发送完成后重新计时
            last_send_time = time.time()

        key = cv2.waitKey(1)

        if key == 27:
            break

    cap.release()
    cv2.destroyAllWindows()

    client.loop_stop()
    client.disconnect()

    print("Program stopped")


if __name__ == "__main__":
    main()