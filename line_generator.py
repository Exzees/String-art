import threading
from time import sleep
import queue
from PIL import Image
import aggdraw
from math import cos, sin, radians
from random import randint
import os


class ImgDrawLines:
    def __init__(self, file_name, dots_count=300, line_count=10000, opacity=26):
        """
        Image string art generator
        Result has be saved format file_name_RES.png

        Args:
            file_name: Path to source image file (JPG/PNG formats supported)
            dots_count: Number of random points to generate (min 2). Default: 300
            line_count: Number of lines to draw between points. Default: 10000
            opacity: Line opacity value (0-255 scale, 0=transparent). Default: 26
        
        Raises:
            ValueError: If invalid arguments are provided
        """
        
        self.file_name = file_name.split('.')[0]
        self.dots_count = dots_count
        self.line_count = line_count
        self.opacity = opacity
        
        self.img = self._transform_img()
        self.size = self.img.size
        self._circle_coords_points = self._generate_circle_points()
        self._line_indexes = self._precompute_line_indexes()
        self.draw_data = self._create_draw_data(self.img)
        self.q = queue.Queue()
        
        self.brush = aggdraw.Brush("grey")
        self.pen = aggdraw.Pen("black", width=1, opacity=self.opacity)
        
        self._worker()


    def _transform_img(self):
        """Image processing and transformation"""
        
        img = Image.open(f"{self.file_name}.jpg")
        width, height = img.size
        
        # Определение области обрезки
        if width > height:
            center = (width - height) // 2
            box = (center, 0, width - center, height)
        else:
            center = (height - width) // 2
            box = (0, center, width, height - center)
        
        # Обрезка и изменение размера
        cropped_img = img.crop(box)
        resized_img = cropped_img.resize((1080, 1080), Image.LANCZOS)
        
        # Конвертация в grayscale
        return resized_img.convert('L')
        


    def _generate_circle_points(self):
        """Generating points on a circle"""
        width, height = self.size
        center = int(width * 0.5)
        radius = width * 0.49
        points = {}
        
        for i in range(self.dots_count):
            angle = radians(360 * i / self.dots_count)
            x = center + int(radius * cos(angle))
            y = center + int(radius * sin(angle))
            points[f'dot{i}'] = (x, y)
            
        return points


    def _precompute_line_indexes(self):
        """Preliminary calculation of indexes for all lines"""
        line_indexes = {}
        dots = list(self._circle_coords_points.keys())
        
        for i in range(len(dots)):
            for j in range(i + 1, len(dots)):
                start_dot = dots[i]
                end_dot = dots[j]
                key = f"dot{i}_dot{j}"
                indexes = self._get_line_indexes(
                    self._circle_coords_points[start_dot],
                    self._circle_coords_points[end_dot]
                )
                line_indexes[key] = indexes
                
        return line_indexes


    def _get_line_indexes(self, start, end):
        """Getting pixel indexes for a line"""
        x0, y0 = start
        x1, y1 = end
        indexes = []
        
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        
        while True:
            idx = self._get_pixel_index((int(x0), int(y0)))
            if idx is not None:
                indexes.append(idx)
                
            if x0 == x1 and y0 == y1:
                break
                
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy
                
        return indexes


    def _get_pixel_index(self, pos):
        """Getting the pixel index by coordinates"""
        x, y = pos
        width, height = self.size
        
        if 0 <= x < width and 0 <= y < height:
            return y * width + x
        return None


    def _create_draw_data(self, image):
        """Initializing drawing data"""
        color_data = image.getdata()
        draw_data = {}
        
        # Собираем все уникальные индексы
        all_indexes = set()
        for indexes in self._line_indexes.values():
            all_indexes.update(indexes)
        
        # Инициализируем данные для рисования
        for idx in all_indexes:
            if idx is not None and idx < len(color_data):
                draw_data[idx] = color_data[idx]
                
        return draw_data


    def _lines_priority(self):
        """Calculating the priority of lines"""
        lines = 0
        start_dot = f'dot{randint(0, self.dots_count - 1)}'
        
        while lines < self.line_count:
            end_dot = self._find_best_line(start_dot)
            self._update_draw_data(start_dot, end_dot)
            self.q.put((
                self._circle_coords_points[start_dot],
                self._circle_coords_points[end_dot]
            ))
            start_dot = end_dot
            lines += 1


    def _find_best_line(self, start_dot):
        """Search for a line with maximum priority"""
        best_end_dot = None
        max_priority = -1
        
        for i in range(self.dots_count):
            end_dot = f'dot{i}'
            if start_dot == end_dot:
                continue
                
            # Формируем ключ с сортированными индексами
            start_idx = int(start_dot[3:])
            end_idx = int(end_dot[3:])
            sorted_key = f"dot{min(start_idx, end_idx)}_dot{max(start_idx, end_idx)}"
            
            # Рассчитываем приоритет
            priority = 0
            for idx in self._line_indexes[sorted_key]:
                if idx in self.draw_data:
                    priority += 255 - self.draw_data[idx]
                    
            priority /= len(self._line_indexes[sorted_key])
            
            if priority > max_priority:
                max_priority = priority
                best_end_dot = end_dot
                
        return best_end_dot


    def _update_draw_data(self, start_dot, end_dot):
        """Updating drawing data for a line"""
        start_idx = int(start_dot[3:])
        end_idx = int(end_dot[3:])
        sorted_key = f"dot{min(start_idx, end_idx)}_dot{max(start_idx, end_idx)}"
        
        for idx in self._line_indexes[sorted_key]:
            if idx in self.draw_data:
                new_value = self.draw_data[idx] + self.opacity
                self.draw_data[idx] = min(new_value, 255)


    def _draw_process(self):
        """The process of drawing lines"""
        self.img = Image.new("RGBA", self.size, (255, 255, 255, 255))
        self.draw = aggdraw.Draw(self.img)
        
        for coords in self._circle_coords_points.values():
            x, y = coords
            self.draw.ellipse([x-1, y-1, x+1, y+1], self.pen, self.brush)
        
        for i in range(self.line_count):
            start, end = self._get_coords()
            self._draw_line(start, end)
            if i % 100 == 0:
                print(f"Lines drawn: {i}/{self.line_count}")
        
        self._save_img()


    def _draw_line(self, start, end):
        """Drawing a single line"""
        x0, y0 = start
        x1, y1 = end
        self.draw.line((x0, y0, x1, y1), self.pen)


    def _get_coords(self):
        """Getting coordinates from a queue"""
        while True:
            try:
                return self.q.get(timeout=1)
            except queue.Empty:
                sleep(0.1)


    def _save_img(self):
        """Saving result"""
        self.draw.flush()
        self.img.save(f"{self.file_name}_RES.png")


    def _worker(self):
        """Starting processing streams"""
        calc_thread = threading.Thread(target=self._lines_priority)
        draw_thread = threading.Thread(target=self._draw_process)
        
        calc_thread.start()
        draw_thread.start()
        
        calc_thread.join()
        draw_thread.join()

