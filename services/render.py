import asyncio
import json
import os
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from playwright.async_api import Browser, BrowserContext, Error, Page, Playwright, async_playwright


APP_UA = (
    "Mozilla/5.0 (Linux; Android 14; 23013RK75C Build/UKQ1.230804.001) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36 "
    "@4399_sykb_android_activity@"
)


PageCallback = Callable[[Page], Awaitable[None]]


@dataclass(slots=True)
class PageRenderService:
    temp_dir: Path = field(default_factory=lambda: Path(tempfile.gettempdir()) / "astrbot_lkwg_toolbox")
    generated_files: set[Path] = field(default_factory=set)
    _cleanup_tasks: set[asyncio.Task[None]] = field(default_factory=set, init=False, repr=False)
    _browser_lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False, repr=False)
    _playwright: Playwright | None = field(default=None, init=False, repr=False)
    _browser: Browser | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self._cleanup_stale_files()

    async def screenshot_locator(
        self,
        *,
        page_url: str,
        locator: str,
        name_prefix: str,
        viewport: dict[str, int] | None = None,
        prepare: PageCallback | None = None,
    ) -> str:
        browser = await self._get_browser()
        context: BrowserContext | None = None
        try:
            context = await self._new_context(browser, viewport=viewport)
            page = await context.new_page()
            await page.goto(page_url, wait_until="load")
            await self._cleanup_common_popups(page)
            if prepare:
                await prepare(page)
            path = self._new_image_path(name_prefix)
            await page.locator(locator).first.screenshot(path=str(path))
            return str(path)
        finally:
            if context is not None:
                await context.close()

    async def wait_images_ready(self, page: Page, selector: str) -> None:
        await page.wait_for_function(
            """
            (selector) => {
                const images = [...document.querySelectorAll(selector)];
                if (images.length === 0) {
                    return true;
                }
                return images.every((img) => img.complete && img.naturalWidth > 0);
            }
            """,
            arg=selector,
        )

    async def fetch_jsonp(self, *, page_url: str, api_url: str, params: dict[str, Any]) -> dict[str, Any]:
        return await asyncio.to_thread(self._fetch_jsonp_sync, page_url, api_url, params)

    async def hydrate_lazy_images(self, page: Page, selector: str) -> None:
        await page.evaluate(
            """
            (selector) => {
                document.querySelectorAll(selector).forEach((img) => {
                    const src = img.getAttribute('data-src');
                    if (src && !img.getAttribute('src')) {
                        img.setAttribute('src', src);
                    }
                });
            }
            """,
            selector,
        )

    async def terminate(self) -> None:
        tasks = list(self._cleanup_tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._cleanup_tasks.clear()

        for path in list(self.generated_files):
            await self.release_file(path)

        async with self._browser_lock:
            browser = self._browser
            playwright_instance = self._playwright
            self._browser = None
            self._playwright = None

        if browser is not None:
            try:
                await browser.close()
            except Error:
                pass
        if playwright_instance is not None:
            await playwright_instance.stop()

    async def release_file(self, path: str | Path) -> None:
        target = Path(path)
        try:
            target.unlink(missing_ok=True)
        except OSError:
            pass
        self.generated_files.discard(target)

    def schedule_file_cleanup(self, path: str | Path, *, delay_seconds: float = 60) -> None:
        task = asyncio.create_task(self._cleanup_file_after_delay(Path(path), delay_seconds))
        self._cleanup_tasks.add(task)
        task.add_done_callback(self._cleanup_tasks.discard)

    async def _cleanup_common_popups(self, page: Page) -> None:
        await page.evaluate(
            """
            () => {
                localStorage.setItem('version_update_pop_version_2026-04-30', '1');
                document.querySelector('#version-update-pop')?.remove();
                document.querySelector('#iwgc_dialog_bg')?.remove();
            }
            """
        )

    async def _cleanup_file_after_delay(self, path: Path, delay_seconds: float) -> None:
        await asyncio.sleep(delay_seconds)
        await self.release_file(path)

    async def _get_browser(self) -> Browser:
        async with self._browser_lock:
            if self._browser is not None and self._browser.is_connected():
                return self._browser
            if self._playwright is None:
                self._playwright = await async_playwright().start()
            self._browser = await self._launch_browser(self._playwright)
            return self._browser

    async def _launch_browser(self, playwright_instance: Playwright) -> Browser:
        launch_kwargs: dict[str, Any] = {
            "headless": True,
        }
        chromium_args = [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
        ]
        extra_args = os.getenv("ASTRBOT_LKWG_CHROMIUM_ARGS", "").strip()
        if extra_args:
            chromium_args.extend(arg for arg in extra_args.split() if arg)
        launch_kwargs["args"] = chromium_args
        try:
            return await playwright_instance.chromium.launch(**launch_kwargs)
        except Error as exc:
            raise RuntimeError(
                "Chromium 启动失败。当前插件会在每次命令时临时启动浏览器截图并立即关闭。"
                "如果运行在 Linux 容器中，请确认除了 `playwright install chromium` 之外，"
                "还安装了系统依赖，例如执行 `playwright install-deps chromium`，"
                "或在镜像中补齐 Playwright 依赖库。原始错误: "
                f"{exc}"
            ) from exc

    async def _new_context(self, browser: Browser, *, viewport: dict[str, int] | None = None) -> BrowserContext:
        context = await browser.new_context(
            user_agent=APP_UA,
            viewport=viewport or {"width": 1280, "height": 2200},
        )
        await context.add_init_script(
            """
            Object.defineProperty(navigator, "userAgent", {
                get: () => arguments[0],
                configurable: true,
            });
            Object.defineProperty(navigator, "appVersion", {
                get: () => arguments[0],
                configurable: true,
            });
            localStorage.setItem("version_update_pop_version_2026-04-30", "1");
            """.replace("arguments[0]", json.dumps(APP_UA))
        )
        return context

    def _new_image_path(self, prefix: str) -> Path:
        path = self.temp_dir / f"{prefix}-{uuid.uuid4().hex}.png"
        self.generated_files.add(path)
        return path

    def _cleanup_stale_files(self, *, max_age_seconds: int = 3600) -> None:
        cutoff = time.time() - max_age_seconds
        for path in self.temp_dir.glob("*.png"):
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink(missing_ok=True)
            except OSError:
                pass

    @staticmethod
    def _fetch_jsonp_sync(page_url: str, api_url: str, params: dict[str, Any]) -> dict[str, Any]:
        query = dict(params)
        callback_name = "__jsonp_callback"
        query["callback"] = callback_name
        req = Request(
            f"{api_url}?{urlencode(query)}",
            headers={
                "User-Agent": APP_UA,
                "Referer": page_url,
            },
        )
        with urlopen(req, timeout=30) as resp:
            payload = resp.read().decode("utf-8", errors="ignore").strip()
        prefix = f"{callback_name}("
        suffix = ");"
        if not payload.startswith(prefix):
            raise RuntimeError("JSONP 响应格式错误")
        if payload.endswith(suffix):
            payload = payload[len(prefix):-len(suffix)]
        elif payload.endswith(")"):
            payload = payload[len(prefix):-1]
        else:
            raise RuntimeError("JSONP 响应格式错误")
        return json.loads(payload)
