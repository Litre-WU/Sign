import asyncio
from httpx import AsyncClient
from time import time, asctime
from datetime import datetime
from calendar import monthrange
from loguru import logger
from fastapi import FastAPI, BackgroundTasks, Body
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request
from typing import Dict, Union
from diskcache import Cache
from json import dumps
import hmac
import hashlib
from base64 import b64encode
from pathlib import Path
from uuid import uuid4

# 使用apscheduler 调用定时任务
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.executors.pool import ThreadPoolExecutor, ProcessPoolExecutor
from apscheduler.jobstores.redis import RedisJobStore

scheduler = AsyncIOScheduler(
    jobstores={
        "default": RedisJobStore(**{
            "host": '127.0.0.1',
            "port": 6379,
            "db": 10,
            "max_connections": 10
        })
    },
    executorsexecutors={
        'default': ThreadPoolExecutor(20),
        'processpool': ProcessPoolExecutor(5),

    },
    job_defaultsjob_defaults={
        'coalesce': False,
        'max_instances': 3
    },
    timezone="Asia/Shanghai")

cache = Cache(str(Path(__file__).parent / "tmp"))

app = FastAPI(title="定时脚本")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 程序开始
@app.on_event("startup")
async def startup_event():
    print("程序开始")
    for k in cache.iterkeys():
        if k.startswith("jd_"):
            if not cache[k]:
                cache.delete("test_pageId")
    # try:
    #     print(scheduler.get_jobs())
    #     # scheduler.remove_all_jobs()
    #     scheduler.start()
    # except Exception as e:
    #     print(f'定时任务启动异常{e}')


# 程序停止
@app.on_event("shutdown")
async def shutdown_event():
    print("程序结束")
    scheduler.shutdown(wait=False)


# 京豆签到
@app.post("/signBeanAct", tags=["京东签到"])
async def api(request: Request, background_tasks: BackgroundTasks,
              pt_pin: Union[str, None] = Body(default="jd_XXX"),
              pt_key: Union[str, None] = Body(default="AAJkPgXXX_XXX")):
    cache.set(pt_pin, pt_key)
    background_tasks.add_task(signBeanAct, **{"pt_pin": pt_pin, "pt_key": pt_key})
    task_id = str(uuid4())
    scheduler.add_job(id=pt_pin, name=f'{pt_pin}', func=signBeanAct, kwargs={"pt_pin": pt_pin, "pt_key": pt_key}, trigger='cron', hour=6, minute=1, replace_existing=True)
    return {"code": 200, "msg": f'{pt_pin} 已更新', "task_id": f'{task_id}'}


# 类token签到签到
@app.post("/{path}", tags=["类token签到"],
          description="南航/csairSign(传入账户的sign_user_token值); 川航/sichuanairSign(传入access-token值); 携程/ctripSign(传入账户的cticket值)")
async def api(request: Request, path: str, background_tasks: BackgroundTasks,
              token: Union[str, None] = Body(default="XXX")):
    result = {"code": 400, "msg": "请检查路由路径!"}
    path_dict = {"csairSign": csairSign, "sichuanairSign": sichuanairSign, "ctripSign": ctripSign}
    if path in path_dict.keys():
        background_tasks.add_task(path_dict[path], **{"token": token})
        scheduler.add_job(id=token, name=f'{token}', func=path_dict[path], kwargs={"token": token}, trigger='cron', hour=6, minute=1, replace_existing=True)
        result.update({"code": 200, "msg": f'{path} {token} 已更新'})
    return result


# 请求函数
async def req(**kwargs):
    url = kwargs.get("url", "")
    if not url: return None
    headers = kwargs.get("headers", {"User-Agent": "okhttp/3.12.1;jdmall;android;version/10.3.4;build/92451;"})
    proxy = None
    proxies = kwargs.get("proxies", {"all://": proxy} if proxy else {})
    try:
        async with AsyncClient(http2=kwargs.get("http2", False), proxies=proxies, headers=headers,
                               cookies=kwargs.get("cookies", {}), verify=False,
                               trust_env=False,
                               follow_redirects=True, timeout=20) as client:
            rs = await client.request(method=kwargs.get("method", "GET"), url=url, params=kwargs.get("params", {}),
                                      data=kwargs.get("data", {}), files=kwargs.get("files", {}),
                                      headers=headers)
            return rs
    except Exception as e:
        logger.error(f'req {url} {e}')
        retry = kwargs.get("retry", 0)
        retry += 1
        if retry > 2:
            return None
        return req(**kwargs | {"retry": retry})


# 钉钉通知
async def dingAlert(**kwargs):
    access_token = kwargs.get("access_token", "")
    secret = kwargs.get("secret", "")
    timestamp = str(round(time() * 1000))
    sign = b64encode(
        hmac.new(secret.encode(), f'{timestamp}\n{secret}'.encode(), digestmod=hashlib.sha256).digest()).decode()
    meta = {
        "method": "POST",
        "url": "https://oapi.dingtalk.com/robot/send",
        "params": {
            "access_token": access_token,
            "timestamp": timestamp,
            "sign": sign,
        },
        "data": dumps({
            'msgtype': 'text',
            'text': {'content': f'{kwargs.get("msg", "测试")} {asctime()}'}
        }),
        "headers": {"Content-Type": "application/json"}
    }
    res = await req(**meta)
    # print(res.text)
    if res and not res.json().get('errcode'):
        return True
    else:
        logger.error(f'{res.text}')
        return False


# 京豆签到
async def signBeanAct(**kwargs):
    pt_key = kwargs.get("pt_key", "")
    pt_pin = kwargs.get("pt_pin", "")
    result = {
        "code": 400,
        "msg": f'请输入pt_key及pt_pin',
        "time": int(time())
    }
    if not all([pt_pin, pt_key]):
        return result
    meta = {
        "method": "POST",
        "url": "https://api.m.jd.com/client.action",
        "params": {
            "functionId": "signBeanAct",
            # "body": '{"fp":"-1","shshshfp":"-1","shshshfpa":"-1","referUrl":"-1","userAgent":"-1","jda":"-1","rnVersion":"3.9"}',
            "appid": "ld",
            "client": "apple",
            # "clientVersion": "10.0.4",
            # "networkType": "wifi",
            # "osVersion": "14.8.1",
            # "uuid": "",
            # "openudid": "",
        },
        "cookies": {
            "pt_key": pt_key,
            "pt_pin": pt_pin
        }
    }
    res = await req(**meta)
    result.update({"msg": f'pt_key: {pt_key}; pt_pin: {pt_pin} 已失效，请重新获取pt_key和pt_pin'})
    if res.status_code == 200:
        text = res.text
        # print(text)
        try:
            res = res.json()
            if res.get("errorMessage"):
                cache.delete(pt_pin)
            else:
                if res["data"]["status"] == '1':
                    result.update({
                        "code": 200,
                        "msg": f'{pt_pin} {res["data"]["newUserAward"]["title"]}' if res["data"].get(
                            "newUserAward") else f"{pt_pin} 今天已签到",
                    })
                else:
                    result.update({
                        "code": 200,
                        "msg": f"京东用户：{pt_pin} 今天已签到",
                    })
        except Exception as e:
            logger.error(f'{text} {e}')
            result.update({"msg": f"京豆签到程序异常 {kwargs}"})
    # 钉钉通知
    logger.info(result)
    await dingAlert(**result)
    return result


# 南航签到
async def csairSign(**kwargs):
    result = {
        "code": 400,
        "msg": f'请输入sign_user_token',
        "time": int(time())
    }
    token = kwargs.get("token", "")
    if not token:
        return result
    cache.set(f'csai_{token}', token)
    # 签到
    createTime = int(time() * 1000)
    meta = {
        "method": "POST",
        "url": "https://wxapi.csair.com/marketing-tools/activity/join",
        "params": {
            "type": "APPTYPE",
            "chanel": "ss",
            "lang": "zh"
        },
        "data": dumps({"activityType": "sign", "channel": "app"}),
        "headers": {"Content-Type": "application/json"},
        "cookies": {"sign_user_token": token}
    }
    res = await req(**meta)
    if res.status_code == 200:
        # text = res.text
        try:
            # {"respCode": "0000", "respMsg": "success", "data": "SEND_OK"}
            info = res.json()
            if info.get("respCode") == "S2001":
                result.update({"code": 200, "msg": f'南航用户：{token} 今天已签到'})
            else:
                # cache.delete(f'csai_{token}')
                result.update({"msg": f'{token} {info.get("respMsg", "")}'})
        except Exception as e:
            logger.error(f'南航签到程序异常 {e}')
            result.update({"msg": f"南航签到程序异常 {kwargs}"})
    logger.info(result)
    # 签到日历
    month_start = datetime(datetime.now().year, datetime.now().month, 1)
    month_end = datetime(datetime.now().year, datetime.now().month,
                         monthrange(datetime.now().year, datetime.now().month)[1])
    meta = {
        "url": "https://wxapi.csair.com/marketing-tools/sign/getSignCalendar",
        "params": {
            "type": "APPTYPE",
            "chanel": "ss",
            "lang": "zh",
            "startQueryDate": str(month_start).split()[0].replace("-", ""),
            "endQueryDate": str(month_end).split()[0].replace("-", "")
        },
        "cookies": {"sign_user_token": token}
    }
    res = await req(**meta)
    if res:
        text = res.text
        try:
            info = res.json()
            if info.get("respCode") == "0000":
                result.update({
                    "code": 200,
                    "msg": f'南航用户：{token} 当月 {info["data"]["dateList"]} 已签到',
                })
            else:
                result.update({"msg": f'{token} {info.get("respMsg", "")}'})
        except Exception as e:
            logger.error(f'{text} {e}')
            result.update({"msg": f"南航签到程序异常 {kwargs}"})
    # 钉钉通知
    logger.info(result)
    await dingAlert(**result)
    return result


# 川航签到
async def sichuanairSign(**kwargs):
    result = {
        "code": 400,
        "msg": f'请输入access-token',
        "time": int(time())
    }
    token = kwargs.get("token", "")
    if not token:
        return result
    cache.set(f'sichuanair_{token}', token)
    meta = {
        "method": "POST",
        "url": "https://fx.sichuanair.com/api/v1/sign/get-sign-rotation",
        "params": {
            "access-token": token
        },
    }
    res = await req(**meta)
    if res.status_code == 200:
        try:
            info = res.json()
            if info.get("code") == 200:
                result.update({"code": 200, "msg": f'川航用户：{token} 今天已签到'})
            else:
                # cache.delete(f'sichuanair_{token}')
                result.update({"msg": f'{token} {info.get("message", "")}'})
        except Exception as e:
            logger.error(f'川航签到程序异常 {e}')
            result.update({"msg": f"南航签到程序异常 {kwargs}"})
    # 钉钉通知
    logger.info(result)
    await dingAlert(**result)
    return result


# 携程签到
async def ctripSign(**kwargs):
    result = {
        "code": 400,
        "msg": f'请输入cticket',
        "time": int(time())
    }
    token = kwargs.get("token", "")
    if not token:
        return result
    token = kwargs["token"]
    cache.set(f'ctrip_{token}', token)
    meta = {
        "method": "POST",
        "url": "https://m.ctrip.com/restapi/soa2/22769/signToday",
        "params": {
            # "_fxpcqlniredt": "09031177218518661420",
            # "x-traceID": "09031177218518661420-1682060530972-8434515"
        },
        "data": dumps({
            # "platform": "H5",
            "openId": "",
            # "rmsToken": "",
            # "head": {
            #     "cid": "09031177218518661420",
            #     "ctok": "",
            #     "cver": "1.0",
            #     "lang": "01",
            #     "sid": "8888",
            #     "syscode": "09",
            #     "auth": "",
            #     "xsid": "",
            #     "extension": []
            # }
        }),
        "cookies": {"cticket": token},
    }
    res = await req(**meta)
    # print(res.text)
    if res and res.status_code == 200:
        msg = res.json()["message"]
        # if res.json()["code"] == "":
        #     cache.delete(f'csai_{token}')
        result.update({
            "code": 200,
            "msg": f'携程用户：{token} {msg}',
        })
    # 钉钉通知
    logger.info(result)
    await dingAlert(**result)
    return result


# 定时任务
async def crontab_task(**kwargs):
    account_list = [
        {
            "pt_key": "XXX",
            "pt_pin": "jd_XXX",
        },
        {
            "pt_key": "XXX",
            "pt_pin": "jd_XXX",
        }
    ]
    # tasks = [asyncio.create_task(signBeanAct(**account_list[i])) for i in range(len(account_list))]
    # tasks = []
    # 京豆任务
    tasks = [asyncio.create_task(signBeanAct(**{"pt_pin": k, "pt_key": cache[k]})) for k in cache.iterkeys() if
             k.startswith("jd_")]
    # 南航任务
    tasks += [asyncio.create_task(csairSign(**{"token": cache[k]})) for k in cache.iterkeys() if k.startswith("csai_")]
    # 川航任务
    tasks += [asyncio.create_task(sichuanairSign(**{"token": cache[k]})) for k in cache.iterkeys() if k.startswith("sichuanair_")]
    # 携程任务
    tasks += [asyncio.create_task(ctripSign(**{"token": cache[k]})) for k in cache.iterkeys() if k.startswith("ctrip_")]

    result_list = await asyncio.gather(*tasks)
    # logger.info(result_list)
    return result_list


if __name__ == '__main__':
    # import uvicorn
    # uvicorn.run(app, host="0.0.0.0", port=8082)
    asyncio.run(crontab_task())
