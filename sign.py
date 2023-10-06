import asyncio
from httpx import AsyncClient
from time import time, sleep, asctime
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
from random import uniform, sample

# 使用apscheduler 调用定时任务
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.executors.pool import ThreadPoolExecutor, ProcessPoolExecutor
# from apscheduler.jobstores.redis import RedisJobStore
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from dateutil.parser import parse
import socket
import argparse


db_path = str(Path(__file__).parent / "tmp")

cache = Cache(db_path)


# 脚本输出参数(crontab执行脚本时使用)
parser = argparse.ArgumentParser(prog="Sign(crontab执行脚本时使用)",
                                 description="crontab定时运行脚本和sqlite数据库未添加情况下，可以通过追加参数添加token值, 多个账户使用';'隔开",
                                 epilog="京东pt_pin和pt_key需同时传入！！！")

parser.add_argument('--pt_pin', help='京东Cookie中获取pt_pin值')
parser.add_argument('--pt_key', help='京东Cookie中获取pt_key值')
parser.add_argument('--csai', help='南航账户的sign_user_token值')
parser.add_argument('--sichuanair', help='川航账户的access-token值')
parser.add_argument('--ctrip', help='携程账户的cticket值')
parser.add_argument('--meituan', help='美团账户的token值')
parser.add_argument('--weimob', help='统一快乐星球账户的X-WX-Token值')
parser.add_argument('--10086', help='中国移动账户的SESSION值')
parser.print_help()

args = parser.parse_args().__dict__

for k, v in args.items():
    if v:
        if k.startswith("pt_"):
            if k == "pt_pin":
                for i, v_ in enumerate(v.split(";")):
                    try:
                        cache.set(v_, args["pt_key"].split(";")[i])
                    except:
                        pass
        else:
            for v_ in v.split(";"):
                cache.set(f'{k}_{v_}', v_)
                

scheduler = AsyncIOScheduler(
    jobstores={
        # "default": RedisJobStore(**{
        #     "host": '127.0.0.1',
        #     "port": 6379,
        #     "db": 10,
        #     "max_connections": 10
        # })
        "default": SQLAlchemyJobStore(url=f'sqlite:///{db_path}/cache.db')
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
    print(f'浏览器访问 http://{socket.gethostbyname(socket.gethostname())}:8082/docs')
    for k in cache.iterkeys():
        if k.startswith("jd_"):
            if not cache[k]:
                cache.delete("test_pageId")
    try:
        scheduler.start()
        print(scheduler.get_jobs())
        scheduler.remove_all_jobs()
    except Exception as e:
        print(f'定时任务启动异常{e}')


# 程序停止
@app.on_event("shutdown")
async def shutdown_event():
    print("程序结束")
    scheduler.shutdown(wait=False)


# 京豆签到
@app.post("/signBeanAct", tags=["京东签到"])
async def api(request: Request, background_tasks: BackgroundTasks,
              pt_pin: Union[str, None] = Body(default="jd_XXX"),
              pt_key: Union[str, None] = Body(default="AAJkPgXXX_XXX"), time: Union[str, None] = Body(default="09:00:00")):
    cache.set(pt_pin, pt_key)
    data_time = parse(time)
    background_tasks.add_task(signBeanAct, **{"pt_pin": pt_pin, "pt_key": pt_key})
    task_id = str(uuid4())
    scheduler.add_job(id=pt_pin, name=f'{pt_pin}', func=signBeanAct, kwargs={"pt_pin": pt_pin, "pt_key": pt_key}, trigger='cron', hour=data_time.hour, minute=data_time.minute, second=data_time.second, replace_existing=True)
    return {"code": 200, "msg": f'{pt_pin} 已更新', "task_id": f'{task_id}'}


# 类token签到签到
@app.post("/{path}", tags=["类token签到"],
          description="南航/csairSign(传入账户的sign_user_token值); 川航/sichuanairSign(传入access-token值); 携程/ctripSign(传入账户的cticket值); 微信龙舟游戏/dragon_boat_2023(传入传入session_token值); 美团优惠券/meituan(传入账户token值); 统一快乐星球/weimob(传入X-WX-Token值); 中国移动/10086(传入SESSION值)")
async def api(request: Request, path: str, background_tasks: BackgroundTasks,
              token: Union[str, None] = Body(default="XXX"), time: Union[str, None] = Body(default="09:00:00")):
    result = {"code": 400, "msg": "请检查路由路径!"}
    data_time = parse(time)
    path_dict = {"csairSign": csairSign, "sichuanairSign": sichuanairSign, "ctripSign": ctripSign, "dragon_boat_2023":dragon_boat_2023, "meituan": meituan, "weimob": weimob, "10086": m10086}
    if path in path_dict.keys():
        background_tasks.add_task(path_dict[path], **{"token": token})
        scheduler.add_job(id=token, name=f'{token}', func=path_dict[path], kwargs={"token": token}, trigger='cron', hour=data_time.hour, minute=data_time.minute, second=data_time.second, replace_existing=True)
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
                                      data=kwargs.get("data", {}), json=kwargs.get("json", {}), files=kwargs.get("files", {}),
                                      headers=headers)
            return rs
    except Exception as e:
        logger.error(f'req {url} {e}')
        retry = kwargs.get("retry", 0)
        retry += 1
        if retry > 2:
            return None
        return await req(**kwargs | {"retry": retry})


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


# 微信龙舟游戏
async def dragon_boat_2023(**kwargs):
    result = {
        "code": 400,
        "msg": f'请输入session_token',
        "time": int(time())
    }
    session_token = kwargs.get("token", "")
    if not session_token:
        return result
    activity_id = 1000005
    # 目标分数及提现额度
    total_score = 10000
    # 获取game_id
    meta = {
        "method": "POST",
        "url": "https://payapp.weixin.qq.com/coupon-center-activity/game/create",
        "params": {
            "session_token": session_token},
        "headers": {
            "Content-Type": "application/json",
            "X-Requested-With": "com.tencent.mm",
        },
        "json": {"activity_id": activity_id, "game_pk_id": ""}
    }
    res = await req(**meta)
    if res:
        res = res.json()
        if res.get("data"):
            game_id = res["data"]["game_id"]
            game_score = 0
            score_items = []
            for tracks in res["data"]["play_script"]["dragon_boat_2023_play_script"]["tracks"]:
                for prop in tracks["props"]:
                    if prop.get("score"):
                        score_items.append({"prop_id": prop["prop_id"], "award_score": prop["score"],
                                            "fetch_timestamp_ms": int(round(time() * 1000))})
                        game_score += prop["score"]
            logger.info(f'游戏ID: {game_id} 游戏总分: {game_score}')
            if game_score < total_score:
                sleep(uniform(0, 0.2))
                return await dragon_boat_2023(**kwargs)
        else:
            logger.error(f'账号状态: {res}')
            cache.delete(f'dragon_boat_2023_{session_token}')
            return res
        cache.set(f'dragon_boat_2023_{session_token}', session_token)
        # 开始游戏
        meta.update({
            "url": "https://payapp.weixin.qq.com/coupon-center-report/statistic/batchreport",
            "json": {
                "source_scene": "scene",
                "device": "DEVICE_ANDROID",
                "device_platform": "DEVICE_ANDROID",
                "device_system": "DEVICE_ANDROID",
                "device_brand": "DEVICE_ANDROID",
                "device_model": "DEVICE_ANDROID",
                "wechat_version": "1.0.0",
                "wxa_sdk_version": "1.0.0",
                "wxa_custom_version": "1.1.6",
                "event_list": [
                    {
                        "event_code": "ActivityGameBegin",
                        "event_target": str(activity_id),
                        "intval1": 2,
                        "strval1": game_id,
                    }
                ],
            }
        })
        res = await req(**meta)
        if res:
            logger.info(f'开始: {res.text}')
        # 游戏间隔时间
        sleep(25)
        # 提交分数
        meta.update({
            "url": "https://payapp.weixin.qq.com/coupon-center-activity/game/report",
            "json": {
                "activity_id": activity_id,
                "game_id": game_id,
                "game_report_score_info": {
                    "score_items": score_items,
                    "game_score": game_score,
                    "total_score": game_score,
                },
            }
        })
        res = await req(**meta)
        if res:
            logger.info(f'提交: {res.text}')
            res = res.json()
            if res.get("msg"):
                return res
        # 获取分数
        meta.update(
            {
                "method": "GET",
                "url": "https://payapp.weixin.qq.com/coupon-center-activity/game/get",
                "params": {
                    "session_token": session_token,
                    "activity_id": "1000000",
                    "game_id": game_id,
                    "sid": "a5299654f1f5e423c1fc9757f9bf071d",
                    "coutom_version": "6.30.6"
                },
                "json": {}
            }
        )
        res = await req(**meta)
        if res:
            logger.info(f'分数: {res.text}')
        # 反馈
        meta.update({
            "method": "POST",
            "url": "https://payapp.weixin.qq.com/coupon-center-activity/award/obtain",
            "params": {
                "session_token": session_token},
            "json": {
                "activity_id": activity_id,
                "game_id": game_id,
                "obtain_ornament": True,
                "request_id": f'osd2L5ZiTu4UDWiNrB8bxnlVB-bQ_lj440mdj_{"".join(sample("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789", 4))}',
                "sid": "3bec088206a229c0cd925c464809cd24",
                "coutom_version": "6.30.8",
            }
        })
        res = await req(**meta)
        if res:
            logger.info(f'反馈: {res.text}')


# 美团
async def meituan(**kwargs):
    result = {
        "code": 400,
        "msg": f'请输入token',
        "time": int(time())
    }
    token = kwargs.get("token", "")
    if not token:
        return result
    meta = {
        "method": "POST",
        "url": "https://mediacps.meituan.com/gundam/gundamGrabV4",
        "json": {"gundamId": 20625, "instanceId": "16807827427780.5322617288978357", "actualLongitude": 108305990,
                 "actualLatitude": 22844501, "needTj": 1,
                 "couponConfigIdOrderCommaString": "3375507571337,3478674735753,3371014554249,3370503570057,3375301526153,3375301722761,3371138220681,3371014881929,3372360729225,620969479,2237835510400,2235023557248,511616988,626467836,621999795,626418652,624362708,1708877283968,1723741504128,511177309,511566737,3242152428169,3801984336521,622936736,603844019,345822793,516213972,3458690974345,622197908,622936732,622740453,622936733,613887410,617540192,588083964,572445327,621999591",
                 "couponAllConfigIdOrderString": "3375507571337,3478674735753,3371014554249,3370503570057,3375301526153,3375301722761,3371138220681,3371014881929,3372360729225,620969479,2237835510400,2235023557248,511616988,626467836,621999795,626418652,624362708,1708877283968,1723741504128,511177309,511566737,3242152428169,3801984336521,622936736,603844019,345822793,516213972,3458690974345,622197908,622936732,622740453,622936733,613887410,617540192,588083964,572445327,621999591",
                 "rubikCouponKey": "PrizePool-200043026", "platform": 13, "app": -1,
                 "h5Fingerprint": "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"},
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.103 Safari/537.36",
            "content-type": "application/json;charset=UTF-8"
        },
        "cookies": {"token": token}
    }
    res = await req(**meta)
    if res:
        cache.set(f'meituan_{token}', token)
        logger.info(res.text)


# 统一快乐星球
async def weimob(**kwargs):
    result = {
        "code": 400,
        "msg": f'请输入X-WX-Token',
        "time": int(time())
    }
    token = kwargs.get("token", "")
    if not token:
        return result
    meta = {
        "method": "POST",
        "url": "https://xapi.weimob.com/api3/onecrm/mactivity/sign/misc/sign/activity/core/c/sign",
        "json": {"appid": "wx532ecb3bdaaf92f9",
                 "basicInfo": {"vid": 6013753979957, "vidType": 2, "bosId": 4020112618957, "productId": 146,
                               "productInstanceId": 3168798957, "productVersionId": "12017",
                               "merchantId": 2000020692957, "tcode": "weimob", "cid": 176205957},
                 "extendInfo": {"wxTemplateId": 7083,
                                "childTemplateIds": [{"customId": 90004, "version": "crm@0.0.159"},
                                                     {"customId": 90002, "version": "ec@31.1"},
                                                     {"customId": 90006, "version": "hudong@0.0.175"},
                                                     {"customId": 90008, "version": "cms@0.0.328"}], "analysis": [],
                                "quickdeliver": {"enable": False}, "bosTemplateId": 1000001061,
                                "youshu": {"enable": False}, "source": 1, "channelsource": 5,
                                "refer": "onecrm-signgift", "mpScene": 1089},
                 "queryParameter": {"tracePromotionId": "100006218", "tracepromotionid": "100006218"},
                 "i18n": {"language": "zh", "timezone": "8"}, "pid": "4020112618957", "storeId": "0",
                 "customInfo": {"source": 0, "wid": 10613173124}, "tracePromotionId": "100006218",
                 "tracepromotionid": "100006218"}
        ,
        "headers": {
            "X-WX-Token": token,
        },
    }
    res = await req(**meta)
    logger.info(res.text)
    if res:
        res = res.json()
        if res["errcode"] == 1041:
            cache.delete(f'weimob_{token}')
        else:
            cache.set(f'weimob_{token}', token)
        result.update({"msg": res.get("errmsg", "")})
        await dingAlert(**result)


# 中国移动
async def m10086(**kwargs):
    result = {
        "code": 400,
        "msg": f'请输入SESSION',
        "time": int(time())
    }
    token = kwargs.get("token", "")
    if not token:
        return result
    # 公众号签到
    meta = {
        "url": "https://wx.10086.cn/qwhdhub/api/mark/do/mark",
        "headers": {
            # "Accept-Charset": "utf-8",
            # "Content-Type": "application/json;charset=UTF-8",
            "x-requested-with": "XMLHttpRequest",
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/20G75 Ariver/1.0.15 leadeon/9.0.0/CMCCIT/tinyApplet WK RVKType(0) NebulaX/1.0.0",
            "login-check": "1",
            "Cookie": f"SESSION={token}",
        }
    }
    res = await req(**meta)
    try:
        if res:
            logger.info(f'公众号签到 {res.text}')
            res = res.json()
            cache.set(f'10086_{token}', token)
            result.update({"msg": f'10086_{token} {res.get("msg", "")}'})

            # app签到
            meta.update({
                "method": "POST",
                "url": "https://wx.10086.cn/qwhdhub/api/mark/mark31/domark",
                "json": {"date": datetime.now().strftime("%Y%m%d")}
            })
            res = await req(**meta)
            logger.info(f'app 签到{res.text}')

            # 任务列表
            meta.update({
                "url": "https://wx.10086.cn/qwhdhub/api/mark/task/taskList",
            })
            res = await req(**meta)
            print(res.text)
            for t in res.json()["data"]["tasks"]:
                taskName, taskId, taskType, jumpUrl = t["taskName"], t["taskId"], t["taskType"], t["jumpUrl"]
                # 任务详情
                meta.update({
                    "url": "https://wx.10086.cn/qwhdhub/api/mark/task/taskInfo",
                    "json": {"taskId": str(taskId)},
                })
                res = await req(**meta)
                logger.info(f'taskInfo {taskName} {taskType} {taskId} {res.text}')

                taskType = res.json()["data"]["taskType"]


                # # 公众号任务 获取回调地址 （需要sid）
                # meta.update({
                #     "url": "https://wx.10086.cn/website/nrapigate/nrmix/activityGroup/getSignTask",
                #     "json": {"ystitle": "", "taskId": str(taskId)},
                # })
                # res = await req(**meta)
                # logger.info(f'getSignTask {taskName} {taskType} {taskId} {res.text}')
                #
                # # 公众号任务完成
                # meta.update({
                #     "url": "https://wx.10086.cn/website/nrapigate/nrmix/activityGroup/finishSignTask",
                #     "json": {"ystitle": "", "taskId": str(taskId)},
                # })
                # res = await req(**meta)
                # logger.info(f'finishSignTask {taskName} {taskType} {taskId} {res.text}')

                # app任务完成
                meta.update({
                    "method": "POST",
                    "url": "https://wx.10086.cn/qwhdhub/api/mark/task/finishTask",
                    "json": {"taskId": str(taskId), "taskType": str(taskType)},
                })
                res = await req(**meta)
                logger.info(f'finishTask {taskName} {taskType} {taskId} {res.text}')

                # 领取奖励
                meta.update({
                    "url": "https://wx.10086.cn/qwhdhub/api/mark/task/getTaskAward",
                    "json": {"taskId": str(t["taskId"])}
                })
                res = await req(**meta)
                logger.info(f'getTaskAward {taskName} {taskType} {taskId} {res.text}')

            # await dingAlert(**result)
    except Exception as e:
        cache.delete(f'10086_{token}')


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
    # 微信龙舟任务
    tasks += [asyncio.create_task(dragon_boat_2023(**{"token": cache[k]})) for k in cache.iterkeys() if k.startswith("dragon_boat_2023_")]
    # 美团优惠券
    tasks += [asyncio.create_task(meituan(**{"token": cache[k]})) for k in cache.iterkeys() if k.startswith("meituan_")]
    # 统一星球
    tasks += [asyncio.create_task(weimob(**{"token": cache[k]})) for k in cache.iterkeys() if k.startswith("weimob_")]
    # 10086
    tasks += [asyncio.create_task(m10086(**{"token": cache[k]})) for k in cache.iterkeys() if k.startswith("10086_")]
    result_list = await asyncio.gather(*tasks)
    # logger.info(result_list)
    return result_list


if __name__ == '__main__':
    # import uvicorn
    # uvicorn.run(app, host="0.0.0.0", port=8082)
    asyncio.run(crontab_task())
