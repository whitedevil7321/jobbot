"""Human-like browser interaction simulation."""
import asyncio
import random
import logging

logger = logging.getLogger(__name__)


async def human_type(page, selector: str, text: str):
    """Type text with human-like delays."""
    await page.click(selector)
    await asyncio.sleep(random.uniform(0.3, 0.7))
    # Clear existing value
    await page.fill(selector, "")
    await asyncio.sleep(random.uniform(0.2, 0.5))
    for char in text:
        await page.type(selector, char, delay=random.randint(50, 180))
        if random.random() < 0.02:  # Occasional pause while typing
            await asyncio.sleep(random.uniform(0.3, 1.0))


async def human_click(page, selector: str):
    """Click with small random offset and delay."""
    element = await page.query_selector(selector)
    if not element:
        return False
    box = await element.bounding_box()
    if box:
        x = box["x"] + box["width"] * random.uniform(0.3, 0.7)
        y = box["y"] + box["height"] * random.uniform(0.3, 0.7)
        await page.mouse.move(x, y, steps=random.randint(5, 15))
        await asyncio.sleep(random.uniform(0.1, 0.3))
        await page.mouse.click(x, y)
    else:
        await page.click(selector)
    await asyncio.sleep(random.uniform(0.3, 0.8))
    return True


async def human_scroll(page, direction: str = "down", amount: int = None):
    """Scroll like a human reading content."""
    if amount is None:
        amount = random.randint(300, 800)
    pixels = amount if direction == "down" else -amount
    # Break into multiple small scrolls
    steps = random.randint(3, 6)
    per_step = pixels // steps
    for _ in range(steps):
        await page.evaluate(f"window.scrollBy(0, {per_step})")
        await asyncio.sleep(random.uniform(0.1, 0.3))


async def random_delay(min_s: float = 0.5, max_s: float = 2.0):
    await asyncio.sleep(random.uniform(min_s, max_s))


async def move_mouse_randomly(page):
    """Move mouse to a random position to simulate natural behavior."""
    viewport = page.viewport_size
    if viewport:
        x = random.randint(100, viewport["width"] - 100)
        y = random.randint(100, viewport["height"] - 100)
        await page.mouse.move(x, y, steps=random.randint(3, 8))
