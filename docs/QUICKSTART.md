# 快速开始

## 1. 无Token体验

下载仓库后双击 `docs/index.html`。它是自包含HTML，可离线打开。调整预算、人数、饮料条件，只筛选5个留存购物篮；不会按人数线性放大历史价格。点击“查看报价证据”可查看时点与检查项。

命令行回放：

```bash
python scripts/rank_quotes.py examples/verified-history.json --replay
```

历史记录跨两个采集时段，回放模式只用于核验记录及展示。实时调用仍要求15分钟内报价。

## 2. 找到真实门店

在 https://open.mcd.cn/mcp 使用自己的麦当劳账号申请Token。工具优先读取 `MCD_MCP_TOKEN`，未设置时通过终端隐藏输入；不要将Token放入命令行参数或Git文件。

创建一个本地参数文件 `private/find-stores.json`：

```json
{"beType": 1, "searchType": 2, "city": "广州", "keyword": "天河城"}
```

改为自己的城市与公开地点关键词，然后：

```bash
python scripts/mcp_readonly.py query-nearby-stores --arguments private/find-stores.json --output private/stores-new.json
```

从成功结果中选择营业中的 `storeCode`。这是到店自取，后续不传 `beCode`。

## 3. 自动组织候选并实时核价

```bash
python scripts/meal_planner.py --store-code 你的门店编号 --people 2 --budget 50 --with-drinks --max-candidates 4 --output-dir private/run-001
```

- 先查询菜单与门店可用券；不会自动使用券。
- 从非随单购卡的主食与饮料中选择小范围候选；名称无法识别的餐品可能不会入选。
- 拉取详情和套餐默认选项，分别试算最多4个完整购物篮。
- 校验请求/返回的商品数量及所有可解释的金额，返回预算内最多3套。

不要求饮料时省略`--with-drinks`。`--people`支持1—6，`--max-candidates`支持1—6。主食覆盖人数只是份数条件，不等于保证吃饱。

## 4. 指定候选餐品

先用`query-meals`获取当前门店的真实编码。`--main-code`和`--drink-code`可各重复多次，它们指定的是候选池，不是保证每个都会被选入。

```bash
python scripts/meal_planner.py --store-code 1400011 --people 2 --budget 50 --with-drinks --main-code 5888 --main-code 9900005470 --drink-code 1088 --output-dir private/run-002
```

上面是2026-10-23早餐时段的真实验收参数；之后可能不再售卖，需要重查。套餐若没有完整默认选项会被跳过，不能擅自猜一个配置。

## 5. 看报告与保存证据

新输出目录包含：

- `report.md`：人可读的候选、应付价、人均与余额。
- `result.json`：筛选结果，不含嵌套原始响应。
- `session.json`：原始菜单、券及报价响应，按私有资料保存。

三个文件均应先按私有资料处理。公开证据应像 `examples/verified-history.json` 一样，只保留必要的公开商品与报价字段；不要直接发布完整会话。

## 6. 测试与打包

```bash
python -m unittest discover -s tests -v
python tools/build_demo.py
python scripts/package_skill.py
```

客户端网络失败、401或429时停止，不密集重试。输入或报价校验失败会显示原因；没有可行方案与网络失败是不同结果。工具不自动创建订单或支付。
