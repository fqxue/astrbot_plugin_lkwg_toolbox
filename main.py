import json
import re
import shlex
from dataclasses import dataclass

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
/lkwg 兑换码统计
/lkwg 蛋组查询 <关键字> [只看异色]
/lkwg 孵蛋查询 <尺寸> <重量>
/lkwg 生蛋规划 演示 [目标精灵]
/lkwg 生蛋规划 路径 <目标精灵> [父本 <父1,父2>] [性别 <公|母>]"""

PLANNER_USAGE = (
    "用法: /lkwg 生蛋规划 演示 [目标精灵]\n"
    "或: /lkwg 生蛋规划 路径 <目标精灵> [父本 <父1,父2>] [性别 <公|母>]"
)


@dataclass(slots=True)
class PlannerArgs:
    target: str
    parents: list[str]
    sex: str


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
                payload = await self.codes.get_codes()
                yield event.plain_result(json.dumps(payload, ensure_ascii=False, indent=2))
            elif action == "兑换码统计":
                payload = await self.codes.get_code_stats()
                yield event.plain_result(json.dumps(payload, ensure_ascii=False, indent=2))
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
        if mode == "演示":
            target = args[1] if len(args) > 1 else None
            path, label = await self.dzfh.render_planner_demo(target)
            async for item in self._send_image(event, f"生蛋规划演示：{target or '默认目标'}（{label}）", path):
                yield item
            return

        if mode == "路径":
            parsed = self._parse_planner_route(args[1:])
            path, label = await self.dzfh.render_planner_route(
                parsed.target,
                parents=parsed.parents,
                sex=parsed.sex,
            )
            parent_text = ",".join(parsed.parents) if parsed.parents else parsed.target
            async for item in self._send_image(
                event,
                f"生蛋规划路径：目标 {parsed.target}，父本 {parent_text}（{label}）",
                path,
            ):
                yield item
            return

        yield event.plain_result(PLANNER_USAGE)

    def _parse_planner_route(self, args: list[str]) -> PlannerArgs:
        if not args:
            raise ValueError(
                "缺少目标精灵。用法: /lkwg 生蛋规划 路径 <目标精灵> [父本 <父1,父2>] [性别 <公|母>]"
            )
        target = args[0]
        parents: list[str] = []
        sex = "male"
        i = 1
        while i < len(args):
            arg = args[i]
            if arg == "父本":
                if i + 1 >= len(args):
                    raise ValueError("父本 后缺少父本列表")
                parents = self.dzfh.normalize_parent_list(args[i + 1])
                i += 2
                continue
            if arg == "性别":
                if i + 1 >= len(args):
                    raise ValueError("性别 后缺少性别值")
                sex_value = args[i + 1].strip().lower()
                sex_map = {
                    "male": "male",
                    "female": "female",
                    "公": "male",
                    "母": "female",
                    "雄": "male",
                    "雌": "female",
                }
                sex = sex_map.get(sex_value, "")
                if sex not in {"male", "female"}:
                    raise ValueError("性别仅支持 公 或 母")
                i += 2
                continue
            raise ValueError(f"未知参数: {arg}")
        return PlannerArgs(target=target, parents=parents, sex=sex)

    async def _send_image(self, event: AstrMessageEvent, title: str, path: str):
        yield event.plain_result(title)
        yield event.image_result(path)

    @staticmethod
    def _extract_tail(message: str) -> str:
        text = (message or "").strip()
        match = re.match(r"^/?lkwg\s*(.*)$", text, re.I)
        if match:
            return match.group(1).strip()
        return text
