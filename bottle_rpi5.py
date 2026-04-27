import cv2
import numpy as np
import time
import os
import glob
import importlib

# ── Import conditionnel picamera2 et RPi.GPIO ──
try:
    from picamera2 import Picamera2
    HAS_PICAMERA = True
except Exception:
    HAS_PICAMERA = False

try:
    import RPi.GPIO as GPIO
    HAS_GPIO = True
except Exception:
    HAS_GPIO = False

# ── Pins GPIO ──
RED_LED_PIN  = 17
BLUE_LED_PIN = 27

# ── Pixel size fonction (requise par le sujet) ──
def pixel_size_meter(working_distance_m, image_width_px=640, image_height_px=480):
    """
    Calcule la taille d un pixel en metres a une distance de travail donnee.
    Camera : Raspberry Pi Camera Module v2 (Sony IMX219)
      Focale          : 3.04 mm
      Capteur         : 3.68 x 2.76 mm
      Resolution native: 3280 x 2464 px
      Pixel pitch natif: 1.12 um
    """
    FOCAL_M        = 0.00304
    SENSOR_WIDTH_M = 0.00368
    SENSOR_HEIGHT_M= 0.00276
    NATIVE_W       = 3280
    NATIVE_H       = 2464

    pitch_x = SENSOR_WIDTH_M  / NATIVE_W
    pitch_y = SENSOR_HEIGHT_M / NATIVE_H
    bin_x   = NATIVE_W / image_width_px
    bin_y   = NATIVE_H / image_height_px
    size_x  = (pitch_x * bin_x * working_distance_m) / FOCAL_M
    size_y  = (pitch_y * bin_y * working_distance_m) / FOCAL_M

    return {
        "pixel_size_x_mm": size_x * 1e3,
        "pixel_size_y_mm": size_y * 1e3,
    }

# ── Mock GPIO ──
class MockGPIO:
    BCM = "BCM"
    OUT = "OUT"
    IN  = "IN"
    _states = {}

    @classmethod
    def setmode(cls, m): pass

    @classmethod
    def setup(cls, pin, direction):
        cls._states[pin] = False

    @classmethod
    def output(cls, pin, value):
        cls._states[pin] = value
        label = {RED_LED_PIN: "LED ROUGE", BLUE_LED_PIN: "LED BLEUE"}.get(pin, f"GPIO{pin}")
        state = "ON" if value else "OFF"
        print(f"  [GPIO MOCK] {label} -> {state}")

    @classmethod
    def input(cls, pin):
        return 1

    @classmethod
    def cleanup(cls):
        cls._states.clear()

# ── Choisir GPIO reel ou mock ──
gpio = GPIO if HAS_GPIO else MockGPIO

# ── Source image : picamera2 ou fichiers ──
class ImageSource:
    def __init__(self, image_folder="images_test"):
        self._picam2  = None
        self._images  = []
        self._idx     = 0

        if HAS_PICAMERA:
            self._picam2 = Picamera2()
            config = self._picam2.create_preview_configuration(
                main={"format": "RGB888", "size": (640, 480)})
            self._picam2.configure(config)
            self._picam2.start()
            time.sleep(0.5)
            print("Camera CSI initialisee.")
        else:
            for ext in ("*.png", "*.jpg", "*.jpeg", "*.bmp"):
                self._images += sorted(glob.glob(os.path.join(image_folder, ext)))
            if not self._images:
                print(f"Aucune image trouvee dans {image_folder}. Creation d images de test...")
                self._create_test_images(image_folder)
                for ext in ("*.png", "*.jpg"):
                    self._images += sorted(glob.glob(os.path.join(image_folder, ext)))
            print(f"Mode fichiers : {len(self._images)} image(s) trouvee(s).")

    def _create_test_images(self, folder):
        os.makedirs(folder, exist_ok=True)

        # Bouteille OK : bouchon bleu, pleine
        img = np.ones((480, 640, 3), dtype=np.uint8) * 180
        cv2.rectangle(img, (240, 80),  (400, 440), (220, 230, 240), -1)
        cv2.rectangle(img, (242, 200), (398, 438), (180, 120, 50),  -1)
        cv2.rectangle(img, (255, 50),  (385, 82),  (200, 80,  30),  -1)
        cv2.imwrite(os.path.join(folder, "bouteille_ok.png"), img)

        # Bouteille vide : bouchon rouge, peu remplie
        img2 = np.ones((480, 640, 3), dtype=np.uint8) * 180
        cv2.rectangle(img2, (240, 80),  (400, 440), (220, 230, 240), -1)
        cv2.rectangle(img2, (242, 400), (398, 438), (180, 120, 50),  -1)
        cv2.rectangle(img2, (255, 50),  (385, 82),  (30,  30,  200), -1)
        cv2.imwrite(os.path.join(folder, "bouteille_vide.png"), img2)

        # Sans bouchon
        img3 = np.ones((480, 640, 3), dtype=np.uint8) * 180
        cv2.rectangle(img3, (240, 80),  (400, 440), (220, 230, 240), -1)
        cv2.rectangle(img3, (242, 200), (398, 438), (180, 120, 50),  -1)
        cv2.imwrite(os.path.join(folder, "sans_bouchon.png"), img3)

        print("Images de test creees : bouteille_ok, bouteille_vide, sans_bouchon.")

    def read(self):
        if self._picam2:
            rgb = self._picam2.capture_array()
            return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        if self._idx >= len(self._images):
            self._idx = 0  # boucle sur les images
        frame = cv2.imread(self._images[self._idx])
        name  = os.path.basename(self._images[self._idx])
        print(f"  [IMAGE] {name}")
        self._idx += 1
        return frame

    def release(self):
        if self._picam2:
            self._picam2.stop()


# ── Traitement image ──
def filter_color(bgr_image, lower_bound_color, upper_bound_color):
    hsv_image = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv_image, lower_bound_color, upper_bound_color)
    return mask


def get_contours(binary_image):
    contours, _ = cv2.findContours(binary_image, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)
    return contours


def detect_cap_color(frame_bgr, min_area=350):
    height, _ = frame_bgr.shape[:2]
    top_h = int(height * 0.45)
    roi = frame_bgr[:top_h, :]

    mask_blue = filter_color(roi, (100, 120, 40), (140, 255, 255))
    mask_red  = cv2.bitwise_or(
        filter_color(roi, (0,   120, 50), (10,  255, 255)),
        filter_color(roi, (170, 120, 50), (180, 255, 255))
    )

    kernel = np.ones((5, 5), np.uint8)
    mask_blue = cv2.morphologyEx(mask_blue, cv2.MORPH_OPEN,  kernel)
    mask_blue = cv2.morphologyEx(mask_blue, cv2.MORPH_CLOSE, kernel)
    mask_red  = cv2.morphologyEx(mask_red,  cv2.MORPH_OPEN,  kernel)
    mask_red  = cv2.morphologyEx(mask_red,  cv2.MORPH_CLOSE, kernel)

    contours_blue = get_contours(mask_blue)
    contours_red  = get_contours(mask_red)

    largest_blue = max((cv2.contourArea(c) for c in contours_blue), default=0)
    largest_red  = max((cv2.contourArea(c) for c in contours_red),  default=0)

    detected_color   = "UNKNOWN"
    detected_contour = None
    contour_color    = (255, 255, 255)

    if largest_blue >= min_area or largest_red >= min_area:
        if largest_blue >= largest_red:
            detected_color   = "BLUE"
            contour_color    = (255, 0, 0)
            detected_contour = max(contours_blue, key=cv2.contourArea)
        else:
            detected_color   = "RED"
            contour_color    = (0, 0, 255)
            detected_contour = max(contours_red, key=cv2.contourArea)

    cap_bbox = None
    if detected_contour is not None:
        x, y, w, h = cv2.boundingRect(detected_contour)
        cap_bbox = (x, y, w, h)
        cv2.rectangle(frame_bgr, (x, y), (x+w, y+h), contour_color, 2)
        cv2.putText(frame_bgr, f"Cap: {detected_color}",
                    (x, max(20, y-8)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, contour_color, 2)
    else:
        cv2.putText(frame_bgr, "Cap: UNKNOWN", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

    return detected_color, cap_bbox


def detect_liquid_level(frame_bgr, cap_bbox):
    height, width = frame_bgr.shape[:2]
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)

    if cap_bbox is None:
        roi_x1 = int(width * 0.30)
        roi_x2 = int(width * 0.70)
        roi_y1 = int(height * 0.22)
    else:
        x, y, w, h = cap_bbox
        cx = x + w // 2
        roi_half_w = max(50, int(1.6 * w))
        roi_x1 = max(0, cx - roi_half_w)
        roi_x2 = min(width - 1, cx + roi_half_w)
        roi_y1 = min(height - 1, y + h + 8)

    roi_y2 = int(height * 0.95)
    if roi_y2 <= roi_y1 or roi_x2 <= roi_x1:
        return None

    roi = gray[roi_y1:roi_y2, roi_x1:roi_x2]
    if roi.size == 0:
        return None

    roi = cv2.GaussianBlur(roi, (5, 5), 0)
    grad_y      = cv2.Sobel(roi, cv2.CV_32F, 0, 1, ksize=3)
    row_scores  = np.median(np.abs(grad_y), axis=1)
    scores_smooth = cv2.GaussianBlur(row_scores.reshape(-1, 1),
                                     (1, 15), 0).reshape(-1)

    h_roi = roi.shape[0]
    search_top    = int(0.10 * h_roi)
    search_bottom = int(0.92 * h_roi)
    if search_bottom <= search_top:
        return None

    window = scores_smooth[search_top:search_bottom]
    if window.size == 0:
        return None

    level_local_y = int(np.argmax(window) + search_top)
    level_y = roi_y1 + level_local_y

    return level_y, roi_x1, roi_x2, roi_y1, roi_y2, (roi_x1, roi_y1, roi_x2, roi_y2)


def set_leds(cap_color):
    if cap_color == "RED":
        gpio.output(RED_LED_PIN,  True)
        gpio.output(BLUE_LED_PIN, False)
    elif cap_color == "BLUE":
        gpio.output(RED_LED_PIN,  False)
        gpio.output(BLUE_LED_PIN, True)
    else:
        gpio.output(RED_LED_PIN,  False)
        gpio.output(BLUE_LED_PIN, False)


def init_gpio():
    gpio.setmode(gpio.BCM)
    gpio.setup(RED_LED_PIN,  gpio.OUT)
    gpio.setup(BLUE_LED_PIN, gpio.OUT)
    gpio.output(RED_LED_PIN,  False)
    gpio.output(BLUE_LED_PIN, False)


def main():
    WORKING_DIST_M   = 0.30
    IMAGE_FOLDER     = "images_test"
    REPORT_INTERVAL  = 1.0

    # Afficher taille pixel
    ps = pixel_size_meter(WORKING_DIST_M)
    print("=" * 50)
    print("  Tri bouteilles — IIA4 / INSAT")
    print(f"  Camera : RPi Camera Module v2")
    print(f"  Distance : {WORKING_DIST_M*100:.0f} cm")
    print(f"  Pixel : {ps['pixel_size_x_mm']:.3f} mm/px")
    print(f"  Mode : {'RPi reel' if HAS_PICAMERA else 'Simulation QEMU'}")
    print("=" * 50)

    src = ImageSource(IMAGE_FOLDER)
    init_gpio()

    last_report_time   = 0.0
    last_cap_color     = None
    last_level_y       = None
    last_fill_pct      = None
    frame_count        = 0

    print("Ctrl+C pour arreter.\n")

    try:
        while True:
            frame = src.read()
            if frame is None:
                break

            frame  = cv2.resize(frame, (640, 480))
            output = frame.copy()
            frame_count += 1

            cap_color, cap_bbox = detect_cap_color(output)
            set_leds(cap_color)

            fill_percentage = None
            level_y         = None
            level = detect_liquid_level(frame, cap_bbox)
            if level is not None:
                level_y, line_x1, line_x2, top, bottom, roi_box = level
                cv2.line(output, (line_x1, level_y), (line_x2, level_y),
                         (0, 255, 255), 2)
                cv2.rectangle(output,
                              (roi_box[0], roi_box[1]),
                              (roi_box[2], roi_box[3]),
                              (0, 200, 0), 1)
                bottle_h = max(1, bottom - top)
                fill_percentage = 100.0 * (bottom - level_y) / bottle_h

            now     = time.time()
            changed = (
                cap_color != last_cap_color
                or level_y != last_level_y
                or (fill_percentage is None) != (last_fill_pct is None)
                or (fill_percentage is not None and last_fill_pct is not None
                    and abs(fill_percentage - last_fill_pct) >= 1.0)
            )

            if changed or (now - last_report_time) >= REPORT_INTERVAL:
                fill_txt  = "N/A" if fill_percentage is None else f"{fill_percentage:.1f}%"
                level_txt = "N/A" if level_y is None else str(level_y)
                print(f"  Frame {frame_count:03d} | Cap: {cap_color:<7} | "
                      f"Level(px): {level_txt:>4} | Fill: {fill_txt}", flush=True)
                last_report_time = now
                last_cap_color   = cap_color
                last_level_y     = level_y
                last_fill_pct    = fill_percentage

            # Pause entre images en mode fichier
            if not HAS_PICAMERA:
                time.sleep(1.5)

    except KeyboardInterrupt:
        print("\nArret par l utilisateur.")

    finally:
        gpio.output(RED_LED_PIN,  False)
        gpio.output(BLUE_LED_PIN, False)
        gpio.cleanup()
        src.release()
        cv2.destroyAllWindows()
        print("Systeme arrete.")


if __name__ == "__main__":
    main()