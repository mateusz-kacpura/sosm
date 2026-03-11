import random
import math
import asyncio
from typing import List, Tuple
from playwright.async_api import Page

class HumanImitation:
    """Implementuje metody zachowań ludzkich dla bota Playwright."""
    
    @staticmethod
    def _bezier_curve(t: float, p0: Tuple[int, int], p1: Tuple[int, int], p2: Tuple[int, int], p3: Tuple[int, int]) -> Tuple[int, int]:
        """Oblicza punkt na sześciennej krzywej Beziera w czasie t (0 do 1)"""
        x = (1 - t)**3 * p0[0] + 3 * (1 - t)**2 * t * p1[0] + 3 * (1 - t) * t**2 * p2[0] + t**3 * p3[0]
        y = (1 - t)**3 * p0[1] + 3 * (1 - t)**2 * t * p1[1] + 3 * (1 - t) * t**2 * p2[1] + t**3 * p3[1]
        return (int(x), int(y))

    @staticmethod
    def _generate_bezier_points(start: Tuple[int, int], end: Tuple[int, int], steps: int = 20) -> List[Tuple[int, int]]:
        """Generuje punkty po drodze na krzywej ignorując liniową podróż"""
        # Punkty kontrolne dla urozmaicenia ścieżki
        dist_x = end[0] - start[0]
        dist_y = end[1] - start[1]
        
        # Dodajemy pewne losowe odchylenia 'brzucha' krzywej
        p1 = (start[0] + int(dist_x * 0.3) + random.randint(-50, 50), start[1] + int(dist_y * 0.2) + random.randint(-50, 50))
        p2 = (start[0] + int(dist_x * 0.7) + random.randint(-50, 50), start[1] + int(dist_y * 0.8) + random.randint(-50, 50))
        
        path = []
        for i in range(steps):
            t = i / (steps - 1)
            point = HumanImitation._bezier_curve(t, start, p1, p2, end)
            path.append(point)
            
        return path

    @staticmethod
    async def natural_mouse_move(page: Page, start_x: int, start_y: int, dest_x: int, dest_y: int):
        """Przeprowadza kursor w miejsce docelowe po krzywej przypominającej ludzki ruch myszą"""
        # Ilość kroków zależna od dystansu by zasymulować odpowiednią prędkość
        distance = math.sqrt((dest_x - start_x)**2 + (dest_y - start_y)**2)
        steps = min(max(int(distance / 20), 10), 50)
        
        path = HumanImitation._generate_bezier_points((start_x, start_y), (dest_x, dest_y), steps)
        
        for point in path:
            await page.mouse.move(point[0], point[1])
            # Ludzkie opóźnienie minimalne miedzy drgnięciami myszy
            await asyncio.sleep(random.uniform(0.01, 0.03))
            
    @staticmethod
    async def type_like_human(page: Page, selector: str, text: str, delay_range: Tuple[float, float] = (0.05, 0.15)):
        """Wpisuje tekst literka po literce, jak człowiek z ew. dłuższymi przerwami."""
        element = await page.wait_for_selector(selector)
        if element:
            await element.click()
            for char in text:
                await page.keyboard.press(char)
                await asyncio.sleep(random.uniform(*delay_range))
            
    @staticmethod
    async def human_delay(min_sec: float = 1.0, max_sec: float = 3.5):
        """Losowo wstrzymuje wykonanie symulując czytanie lub zastanawianie się"""
        await asyncio.sleep(random.uniform(min_sec, max_sec))
        
    @staticmethod
    async def natural_scroll(page: Page, scrolls: int = 3):
        """Sprawia wrażenie czytania lub nawigowania w dół strony / grupy FB"""
        for _ in range(scrolls):
            direction = random.choice([1, -1]) if random.random() < 0.2 else 1 # 80% szans w dół
            distance = random.randint(100, 400) * direction
            await page.mouse.wheel(delta_x=0, delta_y=distance)
            await HumanImitation.human_delay(0.5, 2.0)
