import json
import re
import shlex
from dataclasses import dataclass
from typing import Any

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star

from .services.codes import CodeService
from .services.dzfh import DzfhService
from .services.render import PageRenderService


HELP_TEXT = """用法：
/lkwg 帮助
/lkwg 远行商人
/lkwg 兑换码
/lkwg 蛋组查询 <关键字> [只看异色]
/lkwg 孵蛋查询 <尺寸> <重量>
/lkwg 生蛋规划 路径 <目标精灵> [公 <精灵1,精灵2>] [母 <精灵3,精灵4>]"""

PLANNER_USAGE = (
    "用法: /lkwg 生蛋规划 路径 <目标精灵> [公 <精灵1,精灵2>] [母 <精灵3,精灵4>]"
)


@dataclass(slots=True)
class PlannerSelection:
    name: str
    sex: str


@dataclass(slots=True)
class PlannerArgs:
    target: str
    selections: list[PlannerSelection]


class LkwgToolboxPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.renderer = PageRenderService()
        self.codes = CodeService(self.renderer)
        self.dzfh = DzfhService(self.renderer)

    @filter.command("lkwg")
    async def lkwg(self, event: AstrMessageEvent):
        """洛克王国工具箱总命令。"""
        text = self._extract_tail(event.message_str)
        if not text:
            yield event.plain_result(HELP_TEXT)
            return

        try:
            argv = shlex.split(text)
        except ValueError as exc:
            yield event.plain_result(f"参数解析失败: {exc}")
            return

        if not argv:
            yield event.plain_result(HELP_TEXT)
            return

        action = argv[0]
        args = argv[1:]
        try:
            if action == "帮助":
                yield event.plain_result(HELP_TEXT)
            elif action == "远行商人":
                async for item in self._send_image(event, "远行商人截图", await self.dzfh.render_merchant()):
                    yield item
            elif action == "兑换码":
                yield await self._build_codes_forward(event)
            elif action == "蛋组查询":
                async for item in self._handle_egggroup(event, args):
                    yield item
            elif action == "孵蛋查询":
                async for item in self._handle_hatch(event, args):
                    yield item
            elif action == "生蛋规划":
                async for item in self._handle_planner(event, args):
                    yield item
            else:
                yield event.plain_result(f"未知子命令: {action}\n\n{HELP_TEXT}")
        except Exception as exc:
            logger.exception("lkwg command failed")
            yield event.plain_result(f"执行失败: {exc}")

    async def terminate(self):
        await self.renderer.terminate()

    async def _handle_egggroup(self, event: AstrMessageEvent, args: list[str]):
        if not args:
            yield event.plain_result("用法: /lkwg 蛋组查询 <关键字> [只看异色]")
            return
        only_shiny = any(arg == "只看异色" for arg in args[1:])
        keyword = args[0]
        path = await self.dzfh.render_egggroup(keyword, only_shiny=only_shiny)
        label = f"蛋组查询：{keyword}" + ("（只看异色）" if only_shiny else "")
        async for item in self._send_image(event, label, path):
            yield item

    async def _handle_hatch(self, event: AstrMessageEvent, args: list[str]):
        if len(args) < 2:
            yield event.plain_result("用法: /lkwg 孵蛋查询 <尺寸> <重量>")
            return
        size, weight = args[0], args[1]
        path = await self.dzfh.render_hatch(size, weight)
        async for item in self._send_image(event, f"孵蛋查询：尺寸 {size}，重量 {weight}", path):
            yield item

    async def _handle_planner(self, event: AstrMessageEvent, args: list[str]):
        if not args:
            yield event.plain_result(PLANNER_USAGE)
            return

        mode = args[0]
        if mode == "路径":
            parsed = self._parse_planner_route(args[1:])
            path, label = await self.dzfh.render_planner_route(
                parsed.target,
                selections=[(selection.name, selection.sex) for selection in parsed.selections],
            )
            parent_text = self._format_planner_selections(parsed)
            async for item in self._send_image(
                event,
                f"生蛋规划路径：目标 {parsed.target}，选择 {parent_text}（{label}）",
                path,
            ):
                yield item
            return

        yield event.plain_result(PLANNER_USAGE)

    def _parse_planner_route(self, args: list[str]) -> PlannerArgs:
        if not args:
            raise ValueError(
                "缺少目标精灵。用法: /lkwg 生蛋规划 路径 <目标精灵> [公 <精灵1,精灵2>] [母 <精灵3,精灵4>]"
            )
        target = args[0]
        selections: list[PlannerSelection] = []
        i = 1
        while i < len(args):
            arg = args[i]
            if arg in {"公", "雄"}:
                if i + 1 >= len(args):
                    raise ValueError(f"{arg} 后缺少精灵列表")
                selections.extend(
                    PlannerSelection(name=name, sex="male")
                    for name in self.dzfh.normalize_parent_list(args[i + 1])
                )
                i += 2
                continue
            if arg in {"母", "雌"}:
                if i + 1 >= len(args):
                    raise ValueError(f"{arg} 后缺少精灵列表")
                selections.extend(
                    PlannerSelection(name=name, sex="female")
                    for name in self.dzfh.normalize_parent_list(args[i + 1])
                )
                i += 2
                continue
            raise ValueError(f"未知参数: {arg}")
        return PlannerArgs(target=target, selections=selections)

    @staticmethod
    def _format_planner_selections(parsed: PlannerArgs) -> str:
        if not parsed.selections:
            return f"公 {parsed.target}"

        male_names = [selection.name for selection in parsed.selections if selection.sex == "male"]
        female_names = [selection.name for selection in parsed.selections if selection.sex == "female"]
        parts: list[str] = []
        if male_names:
            parts.append(f"公 {','.join(male_names)}")
        if female_names:
            parts.append(f"母 {','.join(female_names)}")
        return "；".join(parts)

    async def _send_image(self, event: AstrMessageEvent, title: str, path: str):
        yield event.plain_result(title)
        yield event.image_result(path)

    async def _build_codes_forward(self, event: AstrMessageEvent):
        codes = await self.codes.get_codes()
        stats = await self.codes.get_code_stats()
        nodes = []
        for item in codes:
            code_text = str(item.get("code") or item.get("cdkey") or item.get("key") or "").strip()
            if not code_text:
                continue
            nodes.append({
                "type": "node",
                "data": {
                    "name": "洛克王国工具箱",
                    "uin": "0",
                    "content": code_text,
                },
            })

        nodes.append({
            "type": "node",
            "data": {
                "name": "洛克王国工具箱",
                "uin": "0",
                "content": self._format_code_stats(stats),
            },
        })
        return event.chain_result(nodes)

    @staticmethod
    def _format_code_stats(stats: Any) -> str:
        if isinstance(stats, dict):
            lines = ["兑换码统计"]
            for key, value in stats.items():
                lines.append(f"{key}: {value}")
            return "\n".join(lines)
        return f"兑换码统计\n{json.dumps(stats, ensure_ascii=False, indent=2)}"

    @staticmethod
    def _extract_tail(message: str) -> str:
        text = (message or "").strip()
        match = re.match(r"^/?lkwg\s*(.*)$", text, re.I)
        if match:
            return match.group(1).strip()
        return text
