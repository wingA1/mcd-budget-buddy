# 真实 MCP 联调记录

执行日期：2026-10-23，北京时间09:43—09:46。
执行环境：ChatGPT Work / Python标准库HTTP客户端；未使用腾讯WorkBuddy。
测试位置：广州天河城，作为开发验收固定位置，不代表用户所在地或实际点餐意图。
测试门店：麦当劳广州今日广场餐厅，storeCode=1400011；到店自取，orderType=1、beType=1，不传beCode。

## 实际完成的调用

- initialize / tools/list：服务连接成功，发现35个工具。
- now-time-info：业务 success=true，code=200。
- query-nearby-stores：按城市与公开商圈关键词搜索成功，选择营业中的固定验收门店。
- query-meals：成功取得该店当时早餐菜单。
- query-store-coupons：成功，当前门店可用券列表为空；没有领券或假设优惠券。
- query-meal-detail：查询1254与5024成功，均为单品，rounds为空。保留默认特制选项：1254的生菜与5024的吉士，selectedKey均为0-1。
- calculate-price：两套购物篮均success=true，code=200。未购买早餐卡、未传withOrder、未使用优惠券，needTableware=false。

## quote-ham

北京时间09:45:54：火腿扒麦满分×2，price=2200分，即22.00元。productPrice及商品小计总和均为2200分，返回总价与商品小计无差额。

## quote-sausage

北京时间09:45:57：猪柳麦满分×2，price=2800分，即28.00元。productPrice及商品小计总和均为2800分，返回总价与商品小计无差额。

## 排序验证

人数2、总预算50元、无忌口筛选：两套候选均通过筛选，22元方案优先，人均11元，余额28元。预算降为10元时两套均被拒绝。

这是两个主食单品购物篮的真实联调，不包含饮料、小食、营养搭配或过敏安全验证；“两个人吃饱”未经验证。只覆盖本次两套候选，非全菜单最低价保证。报价仅代表当时查询结果，不可作为未来价格承诺。

公开证据见live-price-evidence.json，只保留工具名、公开餐品、价格、公开门店编号与查询时间；未包含Token、用户标识、traceId、地址或个人优惠券。完整响应私有保留，不随发布包交付。

本文件记录最初单品验收。后续默认套餐roundList与独立饮料已在v0.2验证，见LIVE_VALIDATION_V2.md。仍未验证外送、券抵扣和用户指定忌口。
