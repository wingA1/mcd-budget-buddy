# MCP 接入说明

## 实施状态

当前交付包含可供 MCP 宿主执行的 Skill 和离线报价排序器。**已使用参赛者授权完成到店单品路径的真实联调，详见 `docs/LIVE_VALIDATION.md`。外送、套餐及券抵扣尚未验收。**下表为官方公开工具名及计划用途，实际参数以宿主当次发现的 schema 为准，不编造参数字段。

服务：https://mcp.mcd.cn
传输：Streamable HTTP
授权：Authorization 请求头中的 Bearer Token，由参赛者在宿主本地配置。
官方说明：https://github.com/M-China/mcd-mcp-server

| Tool | 用途 | 触发条件 |
| --- | --- | --- |
| `now-time-info` | 确定查询时段 | 开始配餐 |
| `query-nearby-stores` | 到店场景查门店 | 用户提供位置 |
| `delivery-query-addresses` | 查询已有配送地址 | 外送场景且用户授权 |
| `delivery-query-stores` | 查询可配送门店 | 用户选好地址 |
| `query-meals` | 查询选店可售菜单 | 门店已确认 |
| `query-meal-detail` | 核验套餐组成、规格和替换项 | 入选候选 |
| `query-store-coupons` | 查询该店可用优惠券 | 比较候选 |
| `query-my-coupons` | 补充核验用户持有券 | 必要时 |
| `calculate-price` | 核验完整购物篮应付金额 | 每个推荐候选 |

## 调用流程

需求提取 → 确认门店和就餐方式 → 查菜单/详情/可用券 → 构建最多6个候选 → 分别试算 → 将成功报价归一化 → 本地约束筛选 → 返回候选中最多3套方案。

归一化不是通用 API 适配器：本次已取得授权后的schema，并记录关键字段于 `docs/MCP_SCHEMA_NOTES.md`。宿主按真实工具响应提取字段，并保留脱敏引用；字段含义不清时停止，禁止把演示数据作为 fallback。

价格必须来自同门店、同就餐方式、同餐品配置的一次完整购物篮试算。配送费、包装费等费用如不在返回的应付总额中明确体现，则该候选不进入“已核验”推荐。不假设优惠可叠加。

## 业务价值

将“看见优惠”转为“给定人数及总预算下，实际可买的方案”。输出预算余额、应付价与优惠条件，避免用菜单标价冒充到手价。范围有限，不承诺全局最优。

## 权限和信息

不调用 `create-order`、`cancel-order`、`auto-bind-coupons`、积分兑换或抽奖操作。Token仅存本地；仓库不收集位置、地址、手机号和账号原文。401停止并提示更新授权；429停止高频调用。公开证据须手动脱敏并复核，不能直接导出完整账号响应。

## 真实验收

2026-10-23，通过ChatGPT Work中的Python HTTP客户端完成真实调用，成功工具与结果见 `docs/LIVE_VALIDATION.md`；未验收的路径按 `docs/ACCEPTANCE.md` 后续执行。
