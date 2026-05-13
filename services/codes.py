import asyncio
import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.request import Request, urlopen

from .render import PageRenderService


DATA_URL = "https://newsimg.5054399.com/comm/mlcxqcommon/static/wap/js/data_175.js?v=1777882667"
PAGE_URL = "https://www.onebiji.com/tools/lkwgsj/cxq/wap/?immgj=0"
API_URL = "https://www.yxhhdl.com/comm/mlcxqAudit/mlcxq/ajax.php"
TID = 175


@dataclass(slots=True)
class CodeService:
    renderer: PageRenderService

    async def get_codes(self) -> list[dict[str, Any]]:
        text = await asyncio.to_thread(self._fetch_text, DATA_URL)
        match = re.search(r"var\s+mlList\s*=\s*(\[[\s\S]*?\]);", text)
        if not match:
            raise RuntimeError("未找到兑换码列表数据")
        return json.loads(match.group(1))

    async def get_code_stats(self, codes: list[dict[str, Any]]) -> dict[str, Any]:
        ids = [int(item["id"]) for item in codes]
        return await self.renderer.fetch_jsonp(
            page_url=PAGE_URL,
            api_url=API_URL,
            params={
                "op": "getCopy",
                "ids": json.dumps(ids, ensure_ascii=False),
                "tid": TID,
            },
        )

    @staticmethod
    def _fetch_text(url: str) -> str:
        req = Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://www.onebiji.com/",
            },
        )
        with urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", errors="ignore")
