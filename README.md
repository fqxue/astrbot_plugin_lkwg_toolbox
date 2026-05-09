# 洛克王国工具箱 AstrBot 插件

一个用于 AstrBot 的《洛克王国：世界》工具插件，提供兑换码查询、远行商人截图、蛋组查询、孵蛋查询和生蛋规划预览功能。

仓库地址：[fqxue/astrbot_plugin_lkwg_toolbox](https://github.com/fqxue/astrbot_plugin_lkwg_toolbox)

## 快速安装

在 AstrBot 插件管理器中搜索 `astrbot_plugin_lkwg_toolbox` 安装，或通过 Git 克隆：

```powershell
cd AstrBot/data/plugins
git clone https://github.com/fqxue/astrbot_plugin_lkwg_toolbox.git
```

## 环境依赖

确保已安装 Playwright 浏览器内核：

```powershell
playwright install chromium
```

如果运行在 Linux 容器里，通常还需要补系统依赖：

```bash
playwright install-deps chromium
```

插件使用 Playwright 访问网页工具页面并生成截图内容。

## 命令

所有命令都以 `/lkwg` 开头。

```text
/lkwg 帮助
/lkwg 远行商人
/lkwg 兑换码
/lkwg 蛋组查询 <关键字> [只看异色]
/lkwg 孵蛋查询 <尺寸> <重量>
/lkwg 生蛋规划 <目标精灵> [公 <精灵1,精灵2>] [母 <精灵3,精灵4>]
```

## 示例

```text
/lkwg 帮助
/lkwg 远行商人
/lkwg 蛋组查询 喵喵
/lkwg 蛋组查询 火花 只看异色
/lkwg 孵蛋查询 1.20 15.5
/lkwg 生蛋规划 奇丽草
/lkwg 生蛋规划 奇丽草 公 喵喵,火花
/lkwg 生蛋规划 奇丽草 公 喵喵,火花 母 水蓝蓝,迪莫
```

## 输出

- `远行商人 / 蛋组查询 / 孵蛋查询 / 生蛋规划` 返回图片
- `兑换码` 返回合并转发消息，每条兑换码各占一条，最后一条附带兑换码统计

## 说明

- `只看异色` 是中文参数，不需要写英文开关。
- `生蛋规划` 支持同时传入 `公 <...>` 和 `母 <...>` 两组精灵。
- `预约提醒` 未包含在本插件中。
- Linux 容器里如果截图失败，优先检查：
  - 是否执行过 `playwright install chromium`
  - 是否安装过系统依赖 `playwright install-deps chromium`
  - 容器是否允许写 `/tmp`
