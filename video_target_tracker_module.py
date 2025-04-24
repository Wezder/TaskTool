import cv2
import numpy as np
from queue import Empty
from collections import deque
from screeninfo import get_monitors
import time
import math
#from PIL import Image, ImageDraw, ImageFont

# def draw_russian_text(image, text, position, font_path="times.ttf", font_size=30, color=(255, 255, 255)):
#     image_pil = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
#     draw = ImageDraw.Draw(image_pil)
#     font = ImageFont.truetype(font_path, font_size)
#     draw.text(position, text, font=font, fill=color)
#     return cv2.cvtColor(np.array(image_pil), cv2.COLOR_RGB2BGR)

class TrackingVisualizer:
    def __init__(self, window_name="Object Tracking"):
        self.window_name = window_name
        self.selected_target = None
        self.track_history = {}
        self.heat_map = None
        self.statistics = {}
        self.mouse_position = None
        self.current_results = []
        self.selected_history = deque(maxlen=120)  # История для выбранной цели (4 секунды при 30 FPS)

        # Параметры записи
        self.recording = False
        self.recording_start_time = None

        # Параметры заморозки
        self.freeze_enabled = False  # Режим автоматической заморозки
        self.is_frozen = False  # Текущее состояние заморозки
        self.frozen_frame = None  # Сохраненный замороженный кадр
        self.frozen_results = None  # Сохраненные результаты для замороженного кадра
        self.last_frame = None  # Последний обработанный кадр
        self.last_results = None  # Последние результаты

        # Параметры режима остановки (новый режим для кнопки S)
        self.is_stopped = False  # Флаг для режима остановки
        self.stopped_frame = None  # Сохраненный кадр при остановке
        self.stopped_results = None  # Сохраненные результаты при остановке

        # Координаты и данные для расчетов
        self.drone_gps = {"latitude": 0.0, "longitude": 0.0, "altitude": 0.0}
        self.drone_compass = 0.0  # В градусах, 0 - север, по часовой стрелке
        self.drone_pitch = 0.0  # Угол наклона дрона вниз в градусах
        self.drone_fov_h = 53.0  # Горизонтальный угол обзора камеры в градусах
        self.drone_fov_v = 42.0  # Вертикальный угол обзора камеры в градусах
        self.target_distance = 0.0  # Расчетное расстояние до цели в метрах
        self.target_gps = {"latitude": 0.0, "longitude": 0.0}  # Расчетные координаты цели

        # Состояние ввода данных
        self.input_field = None  # Текущее активное поле ввода
        self.input_text = ""  # Текст ввода для активного поля
        self.input_fields = {
            "lat": {"label": "Широта дрона:", "value": "", "x": 10, "y": 200, "width": 280, "active": False},
            "lon": {"label": "Долгота дрона:", "value": "", "x": 10, "y": 240, "width": 280, "active": False},
            "alt": {"label": "Высота дрона (м):", "value": "", "x": 10, "y": 280, "width": 280, "active": False},
            "compass": {"label": "Компас (град):", "value": "", "x": 10, "y": 320, "width": 280, "active": False},
            "pitch": {"label": "Наклон камеры (град):", "value": "", "x": 10, "y": 360, "width": 280,
                      "active": False}
        }

        # Получаем размеры экрана
        screen = get_monitors()[0]
        self.screen_width = screen.width
        self.screen_height = screen.height

        # Устанавливаем размеры окна (70% от размера экрана)
        self.window_width = int(self.screen_width * 0.7)
        self.window_height = int(self.screen_height * 0.7)

        # Параметры для расчета скорости и направления
        self.last_positions = {}
        self.velocities = {}
        self.directions = {}
        self.fps = 30.0  # Предполагаемый FPS для расчетов

        # Флаги для отображения
        self.show_trails = True
        self.show_grid = True
        self.show_info = True

    def initialize_window(self):
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self.window_name, self.window_width, self.window_height)
        cv2.moveWindow(self.window_name,
                       (self.screen_width - self.window_width) // 2,
                       (self.screen_height - self.window_height) // 2)
        cv2.setMouseCallback(self.window_name, self._mouse_callback)

    def toggle_freeze(self):
        """Переключение режима заморозки"""
        self.freeze_enabled = not self.freeze_enabled
        # При выключении режима сбрасываем все связанные состояния
        if not self.freeze_enabled:
            self.is_frozen = False
            self.frozen_frame = None
            self.frozen_results = None
        return self.freeze_enabled

    def toggle_stop(self, frame, results):
        """Переключение режима остановки (по кнопке S)"""
        self.is_stopped = not self.is_stopped

        if self.is_stopped:
            # Сохраняем текущий кадр и результаты
            self.stopped_frame = frame.copy() if frame is not None else None
            self.stopped_results = results.copy() if results else []
            # Добавляем подробные инструкции для пользователя
            print("[INFO] Режим STOP активирован. Инструкция:")
            print("[INFO] 1. Нажмите левой кнопкой мыши на цель для её выбора")
            print("[INFO] 2. Заполните поля с данными дрона:")
            print("[INFO]    - SHIROTA DRONA: широта дрона в градусах")
            print("[INFO]    - DOLGOTA DRONA: долгота дрона в градусах")
            print("[INFO]    - VYSOTA DRONA: высота дрона в метрах")
            print("[INFO]    - KOMPAS: угол компаса в градусах (0=север, по часовой)")
            print("[INFO]    - NAKLON KAMERY: угол наклона камеры вниз в градусах")
            print("[INFO] 3. Между полями можно перемещаться стрелками ВВЕРХ и ВНИЗ")
            print("[INFO] 4. После ввода всех данных, внизу появятся рассчитанные")
            print("[INFO]    координаты цели и расстояние до неё")
            print("[INFO] 5. Для выхода из режима STOP нажмите S ещё раз")

            # Переключаемся на первое поле ввода
            if self.input_fields:
                first_field = list(self.input_fields.keys())[0]
                self.set_active_input_field(first_field)
        else:
            # Очищаем сохраненные данные
            self.stopped_frame = None
            self.stopped_results = None

            # Сбрасываем активное поле ввода
            self.input_field = None
            for field in self.input_fields.values():
                field["active"] = False

            print("[INFO] Режим STOP деактивирован. Видеопоток возобновлен.")

            # Рассчитываем координаты цели, если есть выбранная цель
            if self.selected_target is not None:
                self._calculate_target_location()

        return self.is_stopped

    def set_active_input_field(self, field_name):
        """Устанавливает активное поле ввода"""
        # Деактивируем текущее поле
        if self.input_field:
            self.input_fields[self.input_field]["active"] = False

        # Активируем новое поле
        self.input_field = field_name
        self.input_fields[field_name]["active"] = True
        self.input_text = self.input_fields[field_name]["value"]

    def handle_input_key(self, key):
        """Обрабатывает ввод текста в активное поле"""
        print(f"[DEBUG] Обработка клавиши в режиме ввода, код: {key}")

        if not self.input_field:
            return False

        # Безопасное получение атрибутов со значениями по умолчанию
        visible_fields = getattr(self, 'visible_fields', 3)
        scroll_position = getattr(self, 'scroll_position', 0)

        # Обработка стрелок для навигации между полями
        # Стрелка вверх (различные коды для разных платформ)
        if key in [38, 72, 82, 0x26, 0xff52, 2490368, 65362, 16777235]:
            print("[DEBUG] Обработка стрелки ВВЕРХ")
            field_keys = list(self.input_fields.keys())
            current_index = field_keys.index(self.input_field)

            if current_index > 0:
                # Переходим к предыдущему полю
                prev_field = field_keys[current_index - 1]
                self.set_active_input_field(prev_field)

                # Проверяем, нужно ли прокрутить вверх
                if hasattr(self, 'scroll_position') and current_index <= scroll_position:
                    self.scroll_position = max(0, scroll_position - 1)

                print(f"[INFO] Переход к предыдущему полю: {prev_field}")
            return True

        # Стрелка вниз (различные коды для разных платформ)
        elif key in [40, 80, 84, 0x28, 0xff54, 2621440, 65364, 16777237]:
            print("[DEBUG] Обработка стрелки ВНИЗ")
            field_keys = list(self.input_fields.keys())
            current_index = field_keys.index(self.input_field)

            if current_index < len(field_keys) - 1:
                # Переходим к следующему полю
                next_field = field_keys[current_index + 1]
                self.set_active_input_field(next_field)

                # Проверяем, нужно ли прокрутить вниз
                if hasattr(self, 'scroll_position') and hasattr(self, 'visible_fields'):
                    visible_bottom = scroll_position + visible_fields - 1
                    if current_index >= visible_bottom:
                        self.scroll_position = min(len(field_keys) - visible_fields, scroll_position + 1)

                print(f"[INFO] Переход к следующему полю: {next_field}")
            return True

        elif key == 8 or key == 65288:  # Backspace
            self.input_text = self.input_text[:-1]
            print(f"[DEBUG] Backspace, текст: {self.input_text}")

        elif key == 13 or key == 65293:  # Enter
            # Сохраняем значение
            try:
                # Пробуем преобразовать в число для валидации
                float(self.input_text)
                self.input_fields[self.input_field]["value"] = self.input_text
                print(f"[DEBUG] Enter, сохранено значение: {self.input_text}")

                # Обновляем соответствующее значение в параметрах дрона
                if self.input_field == "lat":
                    self.drone_gps["latitude"] = float(self.input_text)
                elif self.input_field == "lon":
                    self.drone_gps["longitude"] = float(self.input_text)
                elif self.input_field == "alt":
                    self.drone_gps["altitude"] = float(self.input_text)
                elif self.input_field == "compass":
                    self.drone_compass = float(self.input_text)
                elif self.input_field == "pitch":
                    self.drone_pitch = float(self.input_text)

                # Переходим к следующему полю или заканчиваем ввод
                field_keys = list(self.input_fields.keys())
                current_index = field_keys.index(self.input_field)

                if current_index < len(field_keys) - 1:
                    # Переходим к следующему полю
                    next_field = field_keys[current_index + 1]
                    self.set_active_input_field(next_field)

                    # Проверяем, нужно ли прокрутить вниз
                    if hasattr(self, 'scroll_position') and hasattr(self, 'visible_fields'):
                        visible_bottom = scroll_position + visible_fields - 1
                        if current_index >= visible_bottom:
                            self.scroll_position = min(len(field_keys) - visible_fields, scroll_position + 1)
                else:
                    # Завершаем ввод, если это последнее поле
                    self.input_fields[self.input_field]["active"] = False
                    self.input_field = None

                    # Пересчитываем координаты цели
                    self._calculate_target_location()

            except ValueError:
                # Если введено не число, мигаем полем или показываем сообщение
                print("[ERROR] Введите корректное числовое значение")

        elif 32 <= key <= 126:  # Печатные символы ASCII
            # Разрешаем вводить только цифры, точку и минус
            char = chr(key)
            if char.isdigit() or char == '.' or char == '-':
                self.input_text += char
                print(f"[DEBUG] Добавлен символ: {char}, текст: {self.input_text}")

        # Обновляем текущее значение поля
        if self.input_field:
            self.input_fields[self.input_field]["value"] = self.input_text

        return True

    def _calculate_target_location(self):
        """Расчет местоположения цели на основе данных дрона и положения цели на экране"""
        if self.selected_target is None or not self.current_results:
            print("[WARNING] Не выбрана цель для расчета координат")
            return

        # Ищем выбранную цель в текущих результатах
        target_result = None
        for result in self.current_results:
            if result["track_id"] == self.selected_target:
                target_result = result
                break

        if not target_result:
            print("[WARNING] Выбранная цель не найдена в текущих результатах")
            return

        try:
            # Получаем размеры кадра
            frame_height, frame_width = self.current_frame.shape[:2] if self.current_frame is not None else (480, 640)

            # Получаем центр цели
            bbox = target_result["bbox"]
            target_center_x = (bbox[0] + bbox[2]) / 2
            target_center_y = (bbox[1] + bbox[3]) / 2

            # Вычисляем смещение от центра кадра в пикселях
            dx_pixels = target_center_x - frame_width / 2
            dy_pixels = target_center_y - frame_height / 2

            # Конвертируем смещение в пикселях в угловое смещение
            angle_h = (dx_pixels / frame_width) * self.drone_fov_h  # Горизонтальное смещение в градусах
            angle_v = (dy_pixels / frame_height) * self.drone_fov_v  # Вертикальное смещение в градусах

            # Вычисляем полный угол наклона камеры с учетом смещения цели
            pitch_total = self.drone_pitch + angle_v

            # Вычисляем полный угол азимута с учетом смещения цели и направления компаса
            azimuth_total = (self.drone_compass + angle_h) % 360

            # Вычисляем расстояние до цели по высоте и углу наклона
            # h / tan(pitch_total) = расстояние
            pitch_rad = math.radians(pitch_total)
            if pitch_rad > 0:  # Избегаем деления на ноль или отрицательные значения
                self.target_distance = self.drone_gps["altitude"] / math.tan(pitch_rad)
            else:
                self.target_distance = 0  # Или установить какое-то значение по умолчанию

            # Вычисляем GPS координаты цели
            # Используем формулы для примерного расчета на небольших расстояниях
            azimuth_rad = math.radians(azimuth_total)
            lat_rad = math.radians(self.drone_gps["latitude"])

            # Земной радиус в метрах
            earth_radius = 6371000

            # Смещение по широте и долготе в радианах
            delta_lat = (self.target_distance * math.cos(azimuth_rad)) / earth_radius
            delta_lon = (self.target_distance * math.sin(azimuth_rad)) / (earth_radius * math.cos(lat_rad))

            # Конвертируем обратно в градусы
            target_lat = self.drone_gps["latitude"] + math.degrees(delta_lat)
            target_lon = self.drone_gps["longitude"] + math.degrees(delta_lon)

            # Обновляем значения
            self.target_gps["latitude"] = target_lat
            self.target_gps["longitude"] = target_lon

            print(f"\n[INFO] РАСЧЕТ ВЫПОЛНЕН УСПЕШНО!")
            print(f"[INFO] Результаты для цели ID {self.selected_target}:")
            print(f"[INFO] - Расстояние до цели: {self.target_distance:.2f} м")
            print(f"[INFO] - Координаты цели: {target_lat:.6f}, {target_lon:.6f}")
            print(f"[INFO] - Угол наклона с поправкой: {pitch_total:.2f}°")
            print(f"[INFO] - Азимут направления: {azimuth_total:.2f}°")
            print(f"[INFO] Данные доступны в нижней части боковой панели.\n")

        except Exception as e:
            print(f"[ERROR] Ошибка при расчете местоположения цели: {e}")
            import traceback
            print(traceback.format_exc())

    def _check_boundary_collision(self, bbox, frame_shape):
        """Проверка столкновения с границами кадра"""
        if not self.freeze_enabled:
            return False

        margin = 10  # отступ от края в пикселях
        height, width = frame_shape[:2]

        x1, y1, x2, y2 = map(int, bbox)
        return (x1 < margin or x2 > width - margin or
                y1 < margin or y2 > height - margin)

    def _mouse_callback(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            if not hasattr(self, 'current_frame') or self.current_frame is None:
                return

            # Получаем координаты клика с учетом возможного изменения размера окна
            window_rect = cv2.getWindowImageRect(self.window_name)  # x, y, w, h
            window_width = window_rect[2]
            window_height = window_rect[3]

            # Проверяем, не кликнули ли мы по колесу прокрутки
            panel_width = 300  # ширина информационной панели
            panel_area_start = window_width - panel_width

            # Если режим остановки активен и клик в области панели, проверяем клик по полям ввода
            if self.is_stopped and x > panel_area_start:
                panel_x = x - panel_area_start
                panel_y = y

                # Безопасное получение атрибутов прокрутки
                scroll_position = getattr(self, 'scroll_position', 0)
                visible_fields = getattr(self, 'visible_fields', 3)

                # Проверяем клик по индикаторам прокрутки
                if panel_x > panel_width - 30 and 140 < panel_y < 170 and scroll_position > 0:
                    # Клик по верхней стрелке - прокрутка вверх
                    self.scroll_position = max(0, scroll_position - 1)
                    print(f"[DEBUG] Прокрутка вверх, scroll_position = {self.scroll_position}")
                    return

                elif panel_x > panel_width - 30 and panel_y > window_height - 130 and panel_y < window_height - 100:
                    # Клик по нижней стрелке - прокрутка вниз
                    field_keys = list(self.input_fields.keys())
                    max_scroll = max(0, len(field_keys) - visible_fields)
                    self.scroll_position = min(max_scroll, scroll_position + 1)
                    print(f"[DEBUG] Прокрутка вниз, scroll_position = {self.scroll_position}")
                    return

                # Проверяем клик по полям ввода
                field_y_start = 170  # Начальная Y-позиция полей
                field_height = 70  # Высота каждого поля
                field_keys = list(self.input_fields.keys())

                # Только видимые поля
                start_index = min(scroll_position, len(field_keys) - 1)
                end_index = min(start_index + visible_fields, len(field_keys))
                visible_range = range(start_index, end_index)

                for i in visible_range:
                    field_name = field_keys[i]
                    current_y = field_y_start + (i - start_index) * field_height

                    # Проверяем, попал ли клик в область поля ввода
                    field_top = current_y - 5
                    field_bottom = current_y + field_height - 10

                    if field_top <= panel_y <= field_bottom and 5 <= panel_x <= panel_width - 5:
                        print(f"[INFO] Выбрано поле ввода: {field_name}")
                        self.set_active_input_field(field_name)
                        return

                # Если клик не по полю ввода, но в области панели, просто возвращаемся
                return

            if self.current_results:
                min_dist = 1000
                closest_target = None

                for result in self.current_results:
                    bbox = result['bbox']
                    center_x = (bbox[0] + bbox[2]) / 2
                    center_y = (bbox[1] + bbox[3]) / 2
                    dist = np.sqrt((x - center_x) ** 2 + (y - center_y) ** 2)
                    print(dist)

                    if dist < min_dist:
                        min_dist = dist
                        closest_target = result['track_id']

                # Если нашли ближайшую цель и она достаточно близко к клику
                if min_dist < 100:  # Порог расстояния для выбора цели
                    self.selected_target = closest_target
                    self.selected_history.clear()
                    print(f"[INFO] Выбрана цель с ID: {self.selected_target}")
                else:
                    self.selected_target = None
                    print("[INFO] Цель не выбрана")

        elif event == cv2.EVENT_MOUSEWHEEL:
            # Проверяем, активен ли режим остановки
            if self.is_stopped:
                # Безопасное получение атрибутов прокрутки
                scroll_position = getattr(self, 'scroll_position', 0)
                visible_fields = getattr(self, 'visible_fields', 3)

                # В OpenCV flags содержит информацию о направлении прокрутки
                # Обычно положительное значение - прокрутка вверх, отрицательное - вниз
                delta = flags

                # В зависимости от реализации, может потребоваться извлечение delta из flags
                # Например: delta = (flags >> 16) & 0xFFFF

                print(f"[DEBUG] Прокрутка колесом, flags = {flags}")

                field_keys = list(self.input_fields.keys())
                max_scroll = max(0, len(field_keys) - visible_fields)

                if delta > 0:  # Прокрутка вверх
                    self.scroll_position = max(0, scroll_position - 1)
                else:  # Прокрутка вниз
                    self.scroll_position = min(max_scroll, scroll_position + 1)

                print(f"[DEBUG] Новая позиция прокрутки: {self.scroll_position}")

        # Обработка колесика мыши для Linux/GTK
        elif event == 10:  # GTK_SCROLL
            if self.is_stopped:
                # Безопасное получение атрибутов прокрутки
                scroll_position = getattr(self, 'scroll_position', 0)
                visible_fields = getattr(self, 'visible_fields', 3)

                field_keys = list(self.input_fields.keys())
                max_scroll = max(0, len(field_keys) - visible_fields)

                if flags > 0:  # Прокрутка вверх
                    self.scroll_position = max(0, scroll_position - 1)
                    print(f"[DEBUG] Прокрутка вверх (GTK), scroll_position = {self.scroll_position}")
                else:  # Прокрутка вниз
                    self.scroll_position = min(max_scroll, scroll_position + 1)
                    print(f"[DEBUG] Прокрутка вниз (GTK), scroll_position = {self.scroll_position}")

    def update_display(self, frame, tracking_results):
        try:
            if frame is None or len(frame.shape) != 3:
                return None

            # Используем сохраненный кадр и результаты в режиме остановки
            if self.is_stopped and self.stopped_frame is not None:
                display_frame = self.stopped_frame.copy()
                display_results = self.stopped_results if self.stopped_results else []
                self.current_frame = display_frame
                self.current_results = display_results
            else:
                self.current_frame = frame.copy()
                display_frame = frame
                display_results = tracking_results if tracking_results else []
                self.current_results = display_results

            # Логика заморозки кадра (только если не в режиме остановки)
            if not self.is_stopped and self.freeze_enabled:  # Если режим заморозки включен
                if not display_results:  # Если нет целей
                    if not self.is_frozen:  # И кадр еще не заморожен
                        self.is_frozen = True
                        self.frozen_frame = frame.copy()
                        self.frozen_results = []
                    # Используем замороженный кадр
                    display_frame = self.frozen_frame
                    display_results = []  # Используем пустой список результатов
                else:  # Если есть цели
                    self.is_frozen = False
                    self.frozen_frame = None
                    self.frozen_results = None
            elif not self.is_stopped:  # Если режим заморозки выключен и не в режиме остановки
                self.is_frozen = False
                self.frozen_frame = None
                self.frozen_results = None

            # Обновляем статистику
            self._update_statistics(self.current_results)

            # Создаем визуализацию
            visualization = self._create_visualization(display_frame, display_results)

            # Добавляем индикаторы состояния
            self._add_status_indicators(visualization)

            # Создаем панель информации
            info_panel = self._create_info_panel(visualization.shape[0])

            # Добавляем поля ввода при активном режиме остановки
            if self.is_stopped:
                self._draw_input_fields(info_panel)

            # Объединяем и отображаем
            try:
                combined_display = np.hstack((visualization, info_panel))
                cv2.imshow(self.window_name, combined_display)
                return combined_display
            except Exception as e:
                print(f"[ERROR] Ошибка отображения: {e}")
                return None

        except Exception as e:
            print(f"[ERROR] Ошибка в update_display: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return None

    def _draw_input_fields(self, panel):
        """Отрисовка полей ввода данных GPS/компаса при активном режиме остановки"""
        # Очищаем панель полностью - для лучшей читаемости
        panel_height, panel_width = panel.shape[:2]
        cv2.rectangle(panel, (0, 0), (panel_width, panel_height), (0, 0, 0), -1)
        # Статистика
        y_pos = 25
        cv2.putText(panel, f"Vsego tselei: {len(self.current_results)}",
                    (10, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
        # Защита от отсутствия атрибута
        visible_fields = getattr(self, 'visible_fields', 5)
        scroll_position = getattr(self, 'scroll_position', 0)

        # Получаем список ключей полей
        field_keys = list(self.input_fields.keys())

        # Индикаторы прокрутки (если необходимо и поля не помещаются)
        if len(field_keys) > visible_fields:
            if scroll_position > 0:
                # Индикатор вверх (есть скрытые поля выше)
                cv2.arrowedLine(panel, (panel_width - 20, 170), (panel_width - 20, 140),
                                (200, 200, 0), 2, tipLength=0.3)

            if scroll_position + visible_fields < len(field_keys):
                # Индикатор вниз (есть скрытые поля ниже)
                cv2.arrowedLine(panel, (panel_width - 20, panel_height - 130),
                                (panel_width - 20, panel_height - 100),
                                (200, 200, 0), 2, tipLength=0.3)

        # Отображаем видимые поля ввода
        y_pos = 40  # Начальная позиция полей ввода
        field_height = 70  # Высота каждого поля вместе с отступами

        # Определяем, какие поля отображать, и рисуем их
        start_index = min(scroll_position, len(field_keys) - 1)
        end_index = min(start_index + visible_fields, len(field_keys))
        visible_range = range(start_index, end_index)

        for i in visible_range:
            field_name = field_keys[i]
            field = self.input_fields[field_name]
            current_y = y_pos + (i - start_index) * field_height

            # Фон для группы поля
            bg_color = (40, 40, 40) if not field["active"] else (60, 60, 100)
            cv2.rectangle(panel,
                          (5, current_y - 5),
                          (panel_width - 5, current_y + field_height - 10),
                          bg_color, -1)

            # Определяем текст метки
            label_text = ""
            if field_name == "lat":
                label_text = "SHIROTA DRONA:"
            elif field_name == "lon":
                label_text = "DOLGOTA DRONA:"
            elif field_name == "alt":
                label_text = "VYSOTA DRONA (m):"
            elif field_name == "compass":
                label_text = "KOMPAS (grad):"
            elif field_name == "pitch":
                label_text = "NAKLON KAMERY (grad):"

            # Рисуем метку поля
            label_color = (200, 200, 200) if not field["active"] else (255, 255, 255)
            cv2.putText(panel, label_text, (10, current_y + 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, label_color, 1)

            # Рисуем поле ввода
            input_y = current_y + 40
            input_bg_color = (60, 60, 80) if not field["active"] else (80, 100, 150)
            text_color = (220, 220, 220) if not field["active"] else (255, 255, 255)

            # Фон поля ввода
            cv2.rectangle(panel,
                          (10, input_y - 15),
                          (panel_width - 10, input_y + 10),
                          input_bg_color, -1)

            # Рамка поля ввода (выделяем активное поле)
            border_color = (100, 100, 100) if not field["active"] else (100, 200, 255)
            thickness = 1 if not field["active"] else 2
            cv2.rectangle(panel,
                          (10, input_y - 15),
                          (panel_width - 10, input_y + 10),
                          border_color, thickness)

            # Текст значения поля
            cv2.putText(panel, field["value"], (15, input_y + 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, text_color, 1)

        # Отображаем данные о выбранной цели внизу панели
        target_data_y = panel_height - 110

        if self.selected_target is not None:
            # Фон для данных о цели
            cv2.rectangle(panel,
                          (5, target_data_y + 10),
                          (panel_width - 5, target_data_y + 115),
                          (0, 30, 0), -1)

            # Рамка для блока данных
            cv2.rectangle(panel,
                          (5, target_data_y + 10),
                          (panel_width - 5, target_data_y + 115),
                          (0, 150, 70), 1)

            # Данные о цели
            data_y = target_data_y + 40

            # Расстояние
            cv2.putText(panel, f"RASSTOYANIE:", (15, data_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 255, 150), 1)
            cv2.putText(panel, f"{self.target_distance:.2f} m", (180, data_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (150, 255, 200), 1)
            data_y += 25

            # Широта
            cv2.putText(panel, f"SHIROTA TSELI:", (15, data_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 255, 150), 1)
            cv2.putText(panel, f"{self.target_gps['latitude']:.6f}", (180, data_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (150, 255, 200), 1)
            data_y += 25

            # Долгота
            cv2.putText(panel, f"DOLGOTA TSELI:", (15, data_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 255, 150), 1)
            cv2.putText(panel, f"{self.target_gps['longitude']:.6f}", (180, data_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (150, 255, 200), 1)

        # Горячие клавиши внизу панели
        # keys_y = panel_height - 100
        # cv2.rectangle(panel, (0, keys_y - 10), (panel_width, panel_height), (30, 30, 30), -1)

        # cv2.putText(panel, "S - Stop rezhim", (15, keys_y + 20),
        #             cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        # cv2.putText(panel, "C - Ochistit vybor", (15, keys_y + 45),
        #             cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        # cv2.putText(panel, "R - Zapis video", (15, keys_y + 70),
        #             cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        # cv2.putText(panel, "ESC - Vykhod", (15, keys_y + 95),
        #             cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

    def _add_status_indicators(self, frame):
        """Добавление индикаторов состояния на кадр"""
        h, w = frame.shape[:2]

        # Индикатор режима заморозки
        freeze_status = "REZHIM FREEZE: "
        if self.freeze_enabled:
            freeze_status += "[VKLUCHEN]"
            if self.is_frozen:
                freeze_status += " (ZAMOROZHEN)"
                status_color = (0, 0, 255)  # Красный для замороженного состояния
            else:
                freeze_status += " (SLEZHENIE)"
                status_color = (0, 255, 0)  # Зеленый для активного отслеживания
        else:
            freeze_status += "[VYKL]"
            status_color = (128, 128, 128)  # Серый цвет для выключенного режима

        # Индикатор режима остановки (новый)
        stop_status = "REZHIM STOP: "
        if self.is_stopped:
            stop_status += "[AKTIVEN]"
            stop_color = (0, 200, 255)  # Оранжевый для режима остановки
        else:
            stop_status += "[VYKL]"
            stop_color = (128, 128, 128)  # Серый цвет для выключенного режима

        # Отображаем статусы
        y_pos = 30
        cv2.putText(frame, freeze_status, (10, y_pos),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)

        y_pos += 30
        cv2.putText(frame, stop_status, (10, y_pos),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, stop_color, 2)

        # Добавляем индикатор записи
        if self.recording:
            # Пульсирующий красный круг
            radius = 10
            position = (w - radius - 10, radius + 10)
            pulse_value = int(127 + 127 * math.sin(time.time() * 5))
            color = (0, 0, pulse_value)
            cv2.circle(frame, position, radius, color, -1)

            # Добавляем время записи
            if self.recording_start_time is not None:
                elapsed = time.time() - self.recording_start_time
                minutes = int(elapsed // 60)
                seconds = int(elapsed % 60)
                time_text = f"{minutes:02d}:{seconds:02d}"
                cv2.putText(frame, time_text, (w - 70, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

    def _create_visualization(self, frame, results):
        vis_frame = frame.copy()

        # Отрисовка сетки
        if self.show_grid:
            h, w = frame.shape[:2]
            grid_size = 50
            for x in range(0, w, grid_size):
                cv2.line(vis_frame, (x, 0), (x, h), (20, 20, 20), 1)
            for y in range(0, h, grid_size):
                cv2.line(vis_frame, (0, y), (w, y), (20, 20, 20), 1)

        # Отрисовка треков и объектов
        for result in results:
            track_id = result['track_id']
            bbox = result['bbox']

            # Определение цвета в зависимости от выбора цели
            if track_id == self.selected_target:
                color = (0, 0, 255)  # Красный для выбранной цели
                thickness = 3
            else:
                color = (255, 0, 0)  # Синий для остальных
                thickness = 2

            # Обновление истории трека
            if track_id not in self.track_history:
                self.track_history[track_id] = deque(maxlen=60)  # 2 секунды при 30 FPS

            center = (int((bbox[0] + bbox[2]) / 2), int((bbox[1] + bbox[3]) / 2))
            self.track_history[track_id].append((int(center[0]), int(center[1])))

            # Отрисовка траектории
            if self.show_trails and len(self.track_history[track_id]) > 1:
                points = np.array(list(self.track_history[track_id]), dtype=np.int32).reshape((-1, 1, 2))
                cv2.polylines(vis_frame, [points], False, color, 2)

            # Отрисовка bbox и информации
            cv2.rectangle(vis_frame,
                          (int(bbox[0]), int(bbox[1])),
                          (int(bbox[2]), int(bbox[3])),
                          color, thickness)

            # Отрисовка центра объекта
            cv2.circle(vis_frame, center, 4, color, -1)

        return vis_frame

    def _create_info_panel(self, height):
        panel_width = 300
        panel = np.zeros((height, panel_width, 3), dtype=np.uint8)

        def cv2_put_text_ru(img, text, point, font=cv2.FONT_HERSHEY_COMPLEX, font_scale=1, color=(255, 255, 255),
                            thickness=1):
            cv2.putText(img, text, point, font, font_scale, color, thickness, cv2.LINE_AA)

        # Заголовок
        cv2_put_text_ru(panel, "Informatsiya", (10, 30), font_scale=0.7, thickness=2)

        # Статистика
        y_pos = 70
        cv2_put_text_ru(panel, f"Vsego tselei: {len(self.current_results)}",
                        (10, y_pos), font_scale=0.6, thickness=1)

        # Контролы
        controls = [
            ("Goryachie klavishi:", True),
            ("LKM - Vybrat tsel", False),
            ("S - Rezhim stop", False),  # Новая опция
            ("F - Avto-zamorozka", False),
            ("T - Traektorii", False),
            ("G - Setka", False),
            ("I - Informatsiya", False),
            ("C - Ochistit vybor", False),
            ("ESC - Vykhod", False)
        ]

        y_pos = height - (len(controls) * 25 + 10)
        for text, is_header in controls:
            if is_header:
                cv2_put_text_ru(panel, text, (10, y_pos),
                                font_scale=0.6, thickness=2)
            else:
                cv2_put_text_ru(panel, text, (20, y_pos),
                                font_scale=0.5, color=(200, 200, 200), thickness=1)
            y_pos += 25

        return panel

    def _update_statistics(self, results):
        current_time = time.time()

        for result in results:
            track_id = result['track_id']
            bbox = result['bbox']
            center = (float((bbox[0] + bbox[2]) / 2), float((bbox[1] + bbox[3]) / 2))

            if track_id in self.last_positions:
                last_pos, last_time = self.last_positions[track_id]
                dt = current_time - last_time

                if dt > 0:
                    dx = center[0] - last_pos[0]
                    dy = center[1] - last_pos[1]
                    distance = np.sqrt(dx * dx + dy * dy)
                    speed = distance / dt

                    # Сглаживание скорости
                    if track_id in self.velocities:
                        speed = 0.7 * self.velocities[track_id] + 0.3 * speed
                    self.velocities[track_id] = speed

                    # Расчет направления
                    angle = np.arctan2(dy, dx) * 180 / np.pi
                    angle = (angle + 360) % 360

                    if track_id in self.directions:
                        old_angle = self.directions[track_id]
                        diff = (angle - old_angle + 180) % 360 - 180
                        angle = (old_angle + diff * 0.3) % 360

                    self.directions[track_id] = angle

            self.last_positions[track_id] = (center, current_time)

            if track_id == self.selected_target:
                self.selected_history.append(center)

    def toggle_trails(self):
        self.show_trails = not self.show_trails

    def toggle_grid(self):
        self.show_grid = not self.show_grid

    def toggle_info(self):
        self.show_info = not self.show_info

class TrackingUI:
    def __init__(self):
        self.visualizer = TrackingVisualizer()
        self.recording = False
        self.writer = None  # Для записи оригинального видео
        self.writer_viz = None  # Для записи видео с визуализацией
        self.last_key_press = {}
        self.key_cooldown = 0.2  # Задержка между нажатиями клавиш в секундах
        self.last_frame_shape = None
        self.last_frame = None
        self.last_results = None

    def run(self, input_queue, shutdown_event):
        self.visualizer.initialize_window()

        try:
            while not shutdown_event.is_set():
                try:
                    # В режиме остановки пропускаем получение новых кадров
                    if not self.visualizer.is_stopped:
                        frame, results = input_queue.get(timeout=0.1)
                        self.last_frame = frame
                        self.last_results = results
                    else:
                        # Используем последний полученный кадр и результаты
                        frame = self.last_frame
                        results = self.last_results
                        time.sleep(0.01)  # Небольшая задержка, чтобы не загружать CPU

                    if frame is None:
                        continue

                    # Получаем визуализацию с информационной панелью
                    vis_frame = self.visualizer.update_display(frame, results)

                    # Запись обоих видео если активна
                    if self.recording:
                        if self.writer and frame is not None:
                            self.writer.write(frame)
                        if self.writer_viz and vis_frame is not None:
                            self.writer_viz.write(vis_frame)

                    # Обработка клавиш с учетом задержки
                    key = cv2.waitKey(1) & 0xFF
                    current_time = time.time()

                    if key != 255:  # Если была нажата клавиша
                        # Отладочный вывод кода клавиши для всех клавиш
                        print(f"[DEBUG] Нажата клавиша с кодом: {key} (десятичный), 0x{key:02X} (hex)")

                        # Проверяем особые клавиши - клавиша S
                        if (key == 115 or key == 251 or key == 219 or key == 83) and self.visualizer.is_stopped:
                            print(f"[DEBUG] Обработка кнопки S для выхода из режима STOP")
                            is_stopped = self.visualizer.toggle_stop(self.last_frame, self.last_results)
                            print(f"[DEBUG] После toggle_stop, is_stopped = {is_stopped}")
                            continue

                        # Если мы в режиме остановки и текстовый ввод активен,
                        # передаем нажатия клавиш обработчику ввода
                        if self.visualizer.is_stopped and self.visualizer.input_field:
                            self.visualizer.handle_input_key(key)
                        # Иначе обрабатываем стандартные команды
                        elif current_time - self.last_key_press.get(key, 0) > self.key_cooldown:
                            self._handle_key_press(key, frame.shape)
                            self.last_key_press[key] = current_time

                    # Проверка состояния окна
                    if cv2.getWindowProperty(self.visualizer.window_name, cv2.WND_PROP_VISIBLE) < 1:
                        print("[INFO] Окно закрыто пользователем")
                        shutdown_event.set()
                        break

                except Empty:
                    if cv2.getWindowProperty(self.visualizer.window_name, cv2.WND_PROP_VISIBLE) < 1:
                        shutdown_event.set()
                        break
                    continue

        except Exception as e:
            print(f"[ERROR] Ошибка в UI: {e}")
            import traceback
            print(traceback.format_exc())
        finally:
            self._cleanup()

    def _handle_key_press(self, key, frame_shape=None):
        if frame_shape is not None:
            self.last_frame_shape = frame_shape

        if key == 27:  # ESC
            cv2.destroyAllWindows()
            return True

        elif key == 115 or key == 251 or key == 219 or key == 83:  # Переключение режима остановки (новое)
            if self.last_frame is not None:
                is_stopped = self.visualizer.toggle_stop(self.last_frame, self.last_results)
                if not is_stopped:
                    print("[INFO] Режим STOP деактивирован. Видеопоток возобновлен.")
            else:
                print("[WARNING] Нет доступных кадров для режима остановки")

        elif key == 102 or key == 224 or key == 192 or key == 70:  # Переключение режима автоматической заморозки
            is_enabled = self.visualizer.toggle_freeze()
            print("[INFO] Режим автоматической заморозки:",
                  "включен" if is_enabled else "выключен")

        elif key == 116 or key == 84 or key == 229 or key == 197:  # Траектории
            self.visualizer.toggle_trails()
            print("[INFO] Траектории:",
                  "включены" if self.visualizer.show_trails else "выключены")

        elif key == 239 or key == 207 or key == 103 or key == 71:  # Сетка
            self.visualizer.toggle_grid()
            print("[INFO] Сетка:",
                  "включена" if self.visualizer.show_grid else "выключена")

        elif key == 241 or key == 209 or key == 99 or key == 67:  # Очистка выбора
            self.visualizer.selected_target = None
            print("[INFO] Выбранная цель очищена")

        # Обработка навигации в режиме ввода с помощью стрелок
        # Разные коды для стрелок вверх/вниз на разных платформах
        elif self.visualizer.is_stopped and self.visualizer.input_field:
            # Стрелка вверх
            if key == 0x26 or key == 0xff52 or key == 2490368:
                self.visualizer.handle_input_key(key)
            # Стрелка вниз
            elif key == 0x28 or key == 0xff54 or key == 2621440:
                self.visualizer.handle_input_key(key)

        return False

    def _cleanup(self):
        """Очистка ресурсов при завершении работы"""
        if self.writer:
            self.writer.release()
        if self.writer_viz:
            self.writer_viz.release()
        print("[INFO] Запись видео остановлена")

        cv2.destroyAllWindows()
        for _ in range(5):
            cv2.waitKey(1)
        print("[INFO] Ресурсы освобождены")