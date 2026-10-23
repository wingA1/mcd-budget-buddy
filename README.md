# 麦麦预算官 · McD Budget Buddy

为“一个人30元怎么吃”“两个人50元、不要辣”提供门店级预算点餐建议的 Agent Skill。

**当前状态：已完成真实 MCP 到店单品查询、价格试算与排序验证，详见 `docs/LIVE_VALIDATION.md`。项目仓库：https://github.com/wingA1/mcd-budget-buddy 。报名结果以官方活动Issue回复为准。离线演示仍使用明确标记的合成数据。外送、套餐和优惠券抵扣路径尚未真实验收。**

## 功能

- 以人数、总预算、门店、就餐方式和口味为约束，组织有限数量的完整购物篮候选。
- 指导宿主真实调用官方 MCP 查询菜单、优惠和套餐详情，以 `calculate-price` 核验最终应付价。
- 用本地 Python 程序过滤超预算、过期报价、门店不一致、费用未确认和主食份数不足的候选，输出前三个方案。
- 仅做查询与决策辅助，不自动下单或领取优惠券。

目标用户：希望控制单餐预算的上班族、学生及多人一起点餐的用户。主食份数约束不保证饱腹程度。

## 安装 Skill

1. 在支持自定义 Skill 及 Streamable HTTP MCP 的宿主中，配置麦当劳官方 MCP。获取Token入口：https://open.mcd.cn/mcp 。
2. 参考 `mcp-config.example.json`，将真实Token仅保存在宿主本地的安全配置中。`${MCD_MCP_TOKEN}` 是公开示例占位符，并非所有宿主都自动展开环境变量；需要按宿主文档配置。不要直接提交填写了凭证的文件。
3. 将 `skills/mcd-budget-buddy/` 作为技能目录导入宿主。各宿主导入入口不同，以其当前文档为准。让宿主同时能够访问本项目的 `scripts/` 与 `examples/`。脚本不是必选依赖，无法运行脚本时由宿主按 Skill 约束筛选。
4. 确认宿主能列出官方 MCP 工具及 schema，然后执行下文真实验收案例。

本项目提供 `scripts/mcp_readonly.py` 只读MCP客户端。运行 `python scripts/mcp_readonly.py now-time-info --output private/time.json`，按隐藏输入提示填写Token；也支持 `MCD_MCP_TOKEN` 环境变量。其他工具参数通过 `--arguments` 指定JSON文件；当前工具参数说明见 `docs/MCP_SCHEMA_NOTES.md`。输出为私有原始响应，公开前必须脱敏。

本项目不包含模型 API 客户端，也不要求申请 OpenAI API Key；对话由所选宿主提供。

## 先运行离线演示

需要 Python 3.10 或以上，仅使用标准库。项目根目录运行：

```bash
python scripts/rank_quotes.py examples/quotes.demo.json --demo
python -m unittest discover -s tests -v
```

演示会从3个合成候选中筛出45元和49元两套，剔除超出50元预算的55元候选。餐品、门店与金额均非真实麦当劳数据。

## 使用示例

> 使用麦麦预算官：两个人总共50元，到店取餐，不要辣。先问我位置、选定门店，再查询实际菜单和优惠；返回不超过预算的方案，价格必须试算核验。

> 只有30元，想要一个主食和一杯饮料。查不到价格就直接说明，不要编造。

> 把预算改为40元，保持同一家店和取餐方式，重新核验候选。

## 实时报价排序

由宿主将真实 MCP 响应归一化到与 `examples/quotes.demo.json` 相同的 JSON 结构，再执行：

```bash
python scripts/rank_quotes.py /path/to/private-live-quotes.json
```

真实模式使用当前系统时间；每个候选需填 `evidence_type: mcp-live` 与 `evidence_ref`（私有脱敏调用记录引用），不能使用演示时钟。所有费用、优惠适用条件及供应状态需要核验后才能设置确认标记。它只是结构化排序器，不直接连接 MCP，也无法证明调用引用的真实性。真实调用证据必须另行留存。

`items[].main_units_per_item` 代表每份该商品/套餐包含的主食份数；其他字段见样例。`exclude_tags` 为精确标签排除，例如 `spicy`；存在排除条件且标签未知时，程序拒绝该候选。它不能用于证明过敏安全。价格使用人民币元与十进制定点运算，拒绝负数和超过两位小数。

只比较已核验候选，不声称“全菜单最低价”。15分钟为本项目防陈旧策略，不是官方报价有效期。

## 项目文件

| 路径 | 用途 |
| --- | --- |
| `skills/mcd-budget-buddy/SKILL.md` | 宿主执行流程与工具调用边界 |
| `scripts/rank_quotes.py` | 可运行的报价排序逻辑 |
| `tests/test_rank_quotes.py` | 核心约束与输入异常测试 |
| `examples/quotes.demo.json` | 明确标记的合成数据 |
| `MCP_INTEGRATION.md` | 接入设计及真实联调待办 |
| `CONTEST_DECLARATION.md` | 从赛事官方仓库下载的原文 |
| `docs/ACCEPTANCE.md` | 真实验收与脱敏证据模板 |
| `docs/REGISTRATION.md` | 发布步骤与报名正文模板 |
| `docs/DEVELOPMENT.md` | 实际开发来源及当前完成情况 |

## 参赛与发布

官方活动：https://github.com/M-China/mcd-developer-innovation-challenge

报名截止：北京时间2026年10月25日23:59。真实接入验证、公开仓库与指定文档是必要条件。当前真实接入记录已完成，源码在本仓库发布，报名结果以官方活动Issue回复为准。参赛声明保留官方内容；提交前请自行阅读确认其中的承诺。没有使用腾讯 WorkBuddy，因此没有 `workbuddy.md`；若后续真实使用它继续开发，需导出真实记录再参与专项奖励。

该项目非麦当劳官方产品；价格、供应与优惠以官方实时返回为准。未使用官方品牌图片或标志。源码及文档可公开审阅；原创代码及原创文档采用MIT许可证；官方参赛声明保留原有权利及条款，麦当劳服务、数据、商标和其他第三方内容不在本项目的MIT授权范围内。
