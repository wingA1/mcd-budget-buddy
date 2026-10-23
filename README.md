# 麦麦预算官 · McD Budget Buddy

**两个人50元，主食和饮料都要——先把整单价格算清楚。**

基于麦当劳中国官方 MCP 的到店配餐 Skill 与 Python 工具。查询门店菜单、构建有限候选、逐单核价，核对商品编码、数量和费用后，输出预算内方案。

[历史报价体验](docs/index.html) · [快速开始](docs/QUICKSTART.md) · [真实套餐验收](docs/LIVE_VALIDATION_V2.md) · [报名 Issue](https://github.com/M-China/mcd-developer-innovation-challenge/issues/1080)

> 历史体验页可下载仓库后双击 `docs/index.html` 打开，无需Token。GitHub文件页展示源码，不代表已开启在线托管。体验页只筛选真实历史购物篮，不实时查价。

## 已真实跑通的例子

2026-10-23 10:13，广州今日广场餐厅，到店自取，2人、总预算50元、每人一份豆浆：

| 方案 | 餐品 | 整单应付 | 人均 | 余额 |
| --- | --- | ---: | ---: | ---: |
| 单品为主 | 吉士蛋麦满分×2 + 优品豆浆小杯×2 | ¥39.00 | ¥19.50 | ¥11.00 |
| 一份套餐搭配单品 | 吉士蛋麦满分×1 + 雪菜脆笋鸡肉粥套餐×1 + 优品豆浆小杯×2 | ¥44.50 | ¥22.25 | ¥5.50 |
| 两份套餐 | 雪菜脆笋鸡肉粥套餐×2 + 优品豆浆小杯×2 | ¥50.00 | ¥25.00 | ¥0.00 |

当时套餐包含粥、油条和薯饼，不含饮料。三个金额都来自各自完整购物篮的 `calculate-price`，没有用菜单价相加冒充核价。**这些是历史验证值，当前使用必须重新查询。**原始请求及响应的脱敏副本见 [verified-history.json](examples/verified-history.json)。

## v0.2 完善了什么

- **可运行的配餐流程**：查菜单、查券、读默认套餐选项、构建候选、核价、校验、排序、生成 Markdown 报告。
- **原始报价校验**：不仅看 `success=true`，还检查请求与返回的商品编码/数量、逐项小计、整单金额及费用。响应漏项时拒绝报价。
- **拒绝条件低价误用**：自动候选排除随单购卡商品；不擅自领券、购卡或应用优惠券。
- **历史交互体验**：按预算、人数和饮料需求筛选5个真实历史购物篮，查看证据、导出结果、体验标明为合成的漏项反例。
- **离线回归与CI**：合成反例测试、真实脱敏证据回放、演示构建一致性和可独立安装的技能包构建。

## 运行

Python **3.10+**，无需第三方 Python 包；命令在仓库根目录执行。

无需Token，先体验：

```bash
python scripts/rank_quotes.py examples/quotes.demo.json --demo
python scripts/rank_quotes.py examples/verified-history.json --replay
python -m unittest discover -s tests -v
```

`--demo`使用合成数据；`--replay`明确回放真实历史记录。两者都不是实时报价。不加这两个参数时，排序器要求原始请求/响应证据且报价须在15分钟内。

真实配餐（隐藏输入Token；Token申请入口：https://open.mcd.cn/mcp）：

```bash
python scripts/meal_planner.py --store-code 你的门店编号 --people 2 --budget 50 --with-drinks --output-dir private/run-001
```

默认从非随单购卡的菜单中，用餐品名启发式挑选主食和饮料，构建最多4个候选，再分别调用官方整单计价；菜单价仅用于安排查询顺序。可以重复传入 `--main-code`、`--drink-code` 指定可选商品，最多核价6个候选；详细步骤见 [QUICKSTART](docs/QUICKSTART.md)。

实时流程只支持**到店自取**，人数1—6。支持默认套餐组成，遇到缺少默认选项的套餐会跳过。不能将名称启发式当作营养、过敏或饱腹判断。默认不应用任何个人优惠券，券列表仅作查询记录。

私有输出目录包含原始响应 `session.json`、筛选结果 `result.json` 和报告 `report.md`，已经忽略在Git之外。输出目录必须是新目录，以免覆盖之前的记录。

## 在 MCP 宿主中使用 Skill

把 `mcp-config.example.json` 作为格式参考，在宿主本地配置麦当劳 MCP。`${MCD_MCP_TOKEN}` 只是公开占位符，不保证宿主自动展开环境变量。不要提交填写真实凭证后的配置。

构建自包含技能包：

```bash
python scripts/package_skill.py
```

将 `dist/mcd-budget-buddy-skill.zip` 解压并导入支持自定义 Skill 和 Streamable HTTP MCP 的宿主。包内包含 `SKILL.md`、运行脚本及公开样例，不依赖仓库外的文件。宿主导入方式以其当前文档为准；命令行工具也可独立使用，不需要模型API Key。

## 报价为什么可信

| 检查 | 不满足时 |
| --- | --- |
| HTTP/JSON-RPC成功且业务 `success=true, code=200` | 停止该报价 |
| 请求顶层商品来自本店菜单 | 拒绝未知编码 |
| 返回商品与请求的编码及数量一致 | 拒绝漏算、换项或多返商品 |
| 小计之和等于 `productPrice` | 拒绝口径不一致的报价 |
| `price = productPrice + 配送/包装/餐具费用` | 拒绝无法解释的费用或优惠 |
| 展示价格和商品与原始证据一致 | 拒绝被篡改的归一化结果 |

价格用整数分核对，再使用 `Decimal` 转为元。只核验可解释的一致报价，不能据此保证库存；证据内容由调用者提供，本地校验也不构成来源真实性认证。优惠口径无法对账时不勉强输出价格。

## 项目结构

```text
scripts/
  meal_planner.py       实时配餐与报告
  quote_validation.py  原始请求/响应校验
  rank_quotes.py       预算、人数、饮料、时效与证据检查
  mcp_readonly.py      查询及核价白名单客户端
  package_skill.py     自包含技能打包
skills/mcd-budget-buddy/SKILL.md
examples/verified-history.json   脱敏真实历史请求/响应
examples/quotes.demo.json        合成离线数据
web/demo.html                   演示源模板
tools/build_demo.py             校验历史证据并构建演示
docs/index.html                 可双击打开的独立体验页
tests/                          离线回归测试
.github/workflows/verify.yml    CI
```

## 已知边界与参赛说明

- 只搜索有限候选，**不保证全菜单最优**。当前自动主食分类基于餐品名称，支持范围有限；需要精确选择时使用商品编码。
- 未真实验收：外送、优惠券抵扣、用户自定义套餐换项；不支持据此声称这些功能已经可用。
- 不创建订单、不支付、不领券、不扣积分。没有调用库存查询能力，不保证供应状态。
- 历史体验页不收Token、不连接账号，不将留存价格包装成实时结果。
- 活动截止：北京时间2026年10月25日23:59；报名结果以[官方Issue](https://github.com/M-China/mcd-developer-innovation-challenge/issues/1080)回复为准，获奖按官方规则执行。
- 本项目使用ChatGPT Work开发，没有伪造腾讯WorkBuddy记录，不以此申请WorkBuddy专项奖励。

原创代码与原创文档采用MIT许可。官方 [CONTEST_DECLARATION.md](CONTEST_DECLARATION.md) 保持原文；官方声明、服务、数据、商标及第三方内容不属于本项目的MIT授权范围。非麦当劳官方产品。
