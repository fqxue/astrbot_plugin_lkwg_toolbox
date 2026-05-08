import asyncio
import json
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

from playwright.async_api import Browser, BrowserContext, Page, async_playwright


APP_UA = (
    "Mozilla/5.0 (Linux; Android 14; 23013RK75C Build/UKQ1.230804.001) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36 "
    "@4399_sykb_android_activity@"
)


PageCallback = Callable[[Page], Awaitable[None]]


@dataclass(slots=True)
class PageRenderService:
    temp_dir: Path = field(default_factory=lambda: Path(tempfile.gettempdir()) / "astrbot_lkwg_toolbox")
    generated_files: list[Path] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    async def screenshot_locator(
        self,
        *,
        page_url: str,
        locator: str,
        name_prefix: str,
        viewport: dict[str, int] | None = None,
        prepare: PageCallback | None = None,
    ) -> str:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            context = await self._new_context(browser, viewport=viewport)
            page = await context.new_page()
            await page.goto(page_url, wait_until="load")
            await self._cleanup_common_popups(page)
            if prepare:
                await prepare(page)
            path = self._new_image_path(name_prefix)
            await page.locator(locator).first.screenshot(path=str(path))
            await context.close()
            await browser.close()
            return str(path)

    async def fetch_jsonp(self, *, page_url: str, api_url: str, params: dict[str, Any]) -> dict[str, Any]:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            context = await self._new_context(browser, viewport={"width": 1280, "height": 900})
            page = await context.new_page()
            await page.goto(page_url, wait_until="load")
            result = await page.evaluate(
                """
                async ({ apiUrl, params }) => {
                    const callbackName = '__jsonp_' + Math.random().toString(36).slice(2);
                    const search = new URLSearchParams(params);
                    search.set('callback', callbackName);
                    return await new Promise((resolve, reject) => {
                        const script = document.createElement('script');
                        window[callbackName] = (data) => {
                            delete window[callbackName];
                            script.remove();
                            resolve(data);
                        };
                        script.onerror = () => {
                            delete window[callbackName];
                            script.remove();
                            reject(new Error('JSONP 请求失败'));
                        };
                        script.src = apiUrl + '?' + search.toString();
                        document.head.appendChild(script);
                    });
                }
                """,
                {"apiUrl": api_url, "params": params},
            )
            await context.close()
            await browser.close()
            return result

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
        for path in self.generated_files:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass

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
        self.generated_files.append(path)
        return path
