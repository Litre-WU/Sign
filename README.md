# Sign
签到啦

(目前支持京东京豆、南航、川航、携程、微信支付有优惠小程序龙舟游戏刷免费提现券、美团优惠券、统一快乐星球、中国移动)

运行项目

`pip install uvicorn fastapi httpx loguru diskcache apscheduler SQLAlchemy -i https://pypi.doubanio.com/simple/`

`uvicorn sign:app --host 0.0.0.0 --port 8081`

打开 http://127.0.0.1:8081/docs

通过接口添加账户token等

apschedule调度运行,也可使用crontab运行,apschedule调度运行,也可使用crontab运行

后续增加其它平台
