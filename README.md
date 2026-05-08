# 洛克王国工具箱 AstrBot 插件

一个用于 AstrBot 的《洛克王国：世界》工具插件，提供兑换码、远行商人、蛋组查询、孵蛋查询和生蛋规划等功能。

## 安装

1. 将 `astrbot_plugin_lkwg_toolbox/` 放到 AstrBot 的插件目录。
2. 安装依赖：

```powershell
uv add playwright
uv run playwright install chromium
```

## 命令

所有命令都以 `/lkwg` 开头。

```text
/lkwg 帮助
/lkwg 远行商人
/lkwg 兑换码
/lkwg 兑换码统计
/lkwg 蛋组查询 <关键字> [只看异色]
/lkwg 孵蛋查询 <尺寸> <重量>
/lkwg 生蛋规划 演示 [目标精灵]
/lkwg 生蛋规划 路径 <目标精灵> [父本 父1,父2] [性别 公|母]
```

## 输出

- `远行商人 / 蛋组查询 / 孵蛋查询 / 生蛋规划` 返回图片
- `兑换码 / 兑换码统计` 返回 JSON 文本

## 说明

- `只看异色` 是中文参数，不需要写英文开关。
- `生蛋规划` 目前支持演示和参数化预览。
- `预约提醒` 未包含在本插件中。

## 开发

入口文件：`main.py`  
服务模块：`services/`
