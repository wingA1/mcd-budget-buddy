# 真实schema接入笔记

来源：2026-10-23真实调用官方 `tools/list`，共35个工具。仅记录本项目所需字段；后续仍需重新发现schema，不能假定永久不变。

## 到店查询

- `query-nearby-stores`：`beType=1`、`searchType=2`，并填写 `city`、`keyword`。验收固定位置为广州天河城。
- 到店自取的后续查询使用 `storeCode`、`orderType=1`、`beType=1`，**不传 `beCode`**。
- `query-meals`：结果 `data.meals` 为商品编码到详情的映射，`data.categories` 为分类；不要将只有条件才能享受的菜单 `currentPrice` 当成最终报价。
- `query-meal-detail`：以上公共参数外加 `code`。结果 `rounds` 为套餐轮次；`modification` 为特制选项。
- `query-store-coupons`：同一组门店/就餐方式参数，`data` 为可用券数组；本次返回空数组。

## 整篮试算

`calculate-price` 使用公共参数及 `items` 数组，每项含 `productCode`、`quantity`。本次为两个同类单品；默认特制选项来自详情，按 `selectedKey` 原样传入。存在 `unselectedKey` 时，未选项也按工具规则传入。`needTableware=false`。不传`withOrder`，不购买任何卡。

本次实际参数示例（该店当时有效，后续使用需重查商品与供应）：

```json
{
  "storeCode": "1400011",
  "orderType": 1,
  "beType": 1,
  "needTableware": false,
  "items": [{
    "productCode": "1254",
    "quantity": 2,
    "modification": {"values": [{"code": "100168", "key": "0-1", "quantity": 1}]}
  }]
}
```

## 返回解析与金额

JSON-RPC层返回`result`。优先读取 `result.structuredContent` 的业务对象；其 `success=true` 且`code=200`才算业务成功，不能只看HTTP 200或`isError=false`。同一份内容也可能放在 `content[].text` 的说明中，不应通过正则猜价格。

业务 `data.price` 为顶层现价，`productPrice` 为商品现价，`productList[].subtotal` 为商品小计。上述金额及 `deliveryPrice`、`packingPrice`、`tablewarePrice` 的单位为分，使用Decimal除100；不要转换两次。优惠对象 `enjoyed/enjoyable.realDiscount` 的金额描述为元，与`discount`（分）区分。

验收两次响应的`price`分别为2200/2800，且均等于`productPrice`与商品小计之和。费用字段未单独返回，记录为“顶层总价与商品小计无差额”，不延伸为其他场景免配送费或免包装费承诺。

## 客户端边界

`scripts/mcp_readonly.py` 仅允许本次用到的六种查询/试算工具。它是面向开发联调的简单客户端，支持本次服务器返回的JSON及单行data事件，固定协商协议2024-11-05；不实现通用MCP的所有传输及重连能力。外送与套餐使用支持完整MCP的宿主联调。HTTP错误和超时会退出，原始响应文件只应私有保存。使用`--help`查看命令格式。
