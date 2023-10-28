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
import sys
import os


db_path = str(Path(__file__).parent / "tmp")

cache = Cache(db_path)


tip = """
脚本输入参数(crontab执行脚本时使用)
 
 --pt_pin       京东Cookie中获取pt_pin值
 --pt_key       京东Cookie中获取pt_key值
 --csai         南航账户的Cookie中sign_user_token值
 --sichuanair   川航账户的Cookie中access-token值
 --ctrip        携程账户的Cookie中cticket值
 --meituan      美团账户Cookie中的token值
 --weimob       统一快乐星球账户Cookie中的X-WX-Token值
 --10086        中国移动账户Cookie中的SESSION值
 --10010        中国联通账户Cookie中的ecs_token值
  --dp           东鹏账户header中的sid值
 --95516        闪惠账户header中的Authorization值
 
 京东pt_pin和pt_key需同时传入！！！
"""

print(tip)

args = sys.argv

for i, arg in enumerate(args):
    try:
        if arg.startswith("-"):
            k = arg.strip("-")
        v = args[i + 1]
        if v.startswith("-"):
            continue
        if v:
            if k.startswith("pt_"):
                if k == "pt_pin":
                    for i_, v_ in enumerate(v.split(";")):
                        try:
                            cache.set(v_, args[i + 3].split(";")[i_])
                        except:
                            pass
            else:
                for v_ in v.split(";"):
                    cache.set(f'{k}_{v_}', v_)
    except Exception as e:
        pass     


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
    print(f'设备IP: {socket.gethostbyname(socket.gethostname())} 当127.0.0.1无法访问时，可以使用设备ip替换')
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
          description="南航/csairSign(传入账户的sign_user_token值); 川航/sichuanairSign(传入access-token值); 携程/ctripSign(传入账户的cticket值); 微信龙舟游戏/dragon_boat_2023(传入传入session_token值); 美团优惠券/meituan(传入账户token值); 统一快乐星球/weimob(传入X-WX-Token值); 中国移动/10086(传入SESSION值); 中国联通/10010(传入ecs_token值); 东鹏/dp(传入sid值); 闪惠/95516(传入Authorization值)")
async def api(request: Request, path: str, background_tasks: BackgroundTasks,
              token: Union[str, None] = Body(default="XXX"), time: Union[str, None] = Body(default="09:00:00")):
    result = {"code": 400, "msg": "请检查路由路径!"}
    data_time = parse(time)
    path_dict = {"csairSign": csairSign, "sichuanairSign": sichuanairSign, "ctripSign": ctripSign, "dragon_boat_2023":dragon_boat_2023, "meituan": meituan, "weimob": weimob, "10086": m10086, "10010": m10010, "dp": youzan_dp, "95516": m95516}
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
    if access_token and secret:
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
        "json": {
            "activityType": "sign",
            "channel": "app",
            "entrance": None
        },
        "headers": {"Content-Type": "application/json"},
        "cookies": {
            "sign_user_token": token,
            "TOKEN": token,
            "cs1246643sso": token,
        }
    }
    res = await req(**meta)
    if res.status_code == 200:
        try:
            info = res.json()
            if info.get("respCode") == "S00011":
                result.update({"code": 200, "msg": f'南航用户：{token} 检查token是否有效'})
                cache.delete(f'csai_{token}')
            if info.get("respCode") == "S2001":
                result.update({"code": 200, "msg": f'南航用户：{token} 今天已签到！'})
            else:
                result.update({"msg": f'{token} {info.get("respMsg", "")}'})
            # 奖励列表
            meta.update({
                "url": "https://wxapi.csair.com/marketing-tools/award/awardList",
                "json": {"activityType": "sign", "awardStatus": "waitReceive", "pageNum": 1, "pageSize": 100},
            })
            res = await req(**meta)
            if res.status_code == 200:
                for d in res.json()["data"]["list"]:
                    logger.info(d["id"])
                    meta.update({
                        "url": "https://wxapi.csair.com/marketing-tools/award/getAward",
                        "json": {"activityType": "sign", "signUserRewardId": d["id"]},
                    })
                    res = await req(**meta)
                    if res.status_code == 200:
                        logger.info(res.json()["data"]["result"])
        except Exception as e:
            logger.error(f'南航签到程序异常 {e}')
            result.update({"msg": f"南航签到程序异常 {kwargs}"})
    logger.info(result)
    # 签到日历
    month_start = datetime(datetime.now().year, datetime.now().month, 1).strftime("%Y%m%d")
    month_end = datetime(datetime.now().year, datetime.now().month,
                         monthrange(datetime.now().year, datetime.now().month)[1]).strftime("%Y%m%d")
    meta = {
        "url": "https://wxapi.csair.com/marketing-tools/sign/getSignCalendar",
        "params": {
            "type": "APPTYPE",
            "chanel": "ss",
            "lang": "zh",
            "startQueryDate": month_start,
            "endQueryDate": month_end
        },
        "cookies": {"sign_user_token": token}
    }
    res = await req(**meta)
    if res:
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
                cache.delete(f'sichuanair_{token}')
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
    cache.set(f'meituan_{token}', token)
    meta = {
        "method": "POST",
        "url": "https://mediacps.meituan.com/gundam/gundamGrabV4",
        "params": {
            "yodaReady": "h5",
            "csecplatform": "4",
            "csecversion": "2.2.1",
            "mtgsig": {"a1": "1.1", "a2": 1697448144738,
                       "a3": "u626yx251w20527zyu3u86u04986u3u581y62xzuyu597958zz4xw60z",
                       "a5": "El5tTKIDIoaunAdQRzBvNtJBlIIZKjUZLZ==",
                       "a6": "hs1.4a4gsvX1s4RLQYqBR3sFhAcJZUrn8+3VWbJ+meaysJ2qQF48MWzawMI/8cXpLkxCgeHru+9OaWxcRKi7x76XJ3HkJvJ3GxbJAa4mOXU4A8LE=",
                       "x0": 4, "d1": "0b94373b8946cbddef86192182d2fcfd"}},
        "data": """{"gundamId":531693,"instanceId":"16970942475020.88256599968703330","actualLongitude":113404419,"actualLatitude":23163929,"needTj":true,"couponConfigIdOrderCommaString":"620969479,2189245219456,2237835510400,4298495230601,10393817973385,8650758750857,9217094451849,9769502114441,9285949325961,7458408104585,11075935339145,4987378139785,9219588883081,8368840966793,7285182431881,7349815083657,9123712533129,7281017291401,9218550006409,7282280694409,5513815065225,603844019,11131204469385,9137512120969,11040176931465,516213972,622936732,622197908,622740453,10494188389001,10495566742153","couponAllConfigIdOrderString":"620969479,2189245219456,2237835510400,4298495230601,10393817973385,8650758750857,9217094451849,9769502114441,9285949325961,7458408104585,11075935339145,4987378139785,9219588883081,8368840966793,7285182431881,7349815083657,9123712533129,7281017291401,9218550006409,7282280694409,5513815065225,603844019,11131204469385,9137512120969,11040176931465,516213972,622936732,622197908,622740453,10494188389001,10495566742153","rubikCouponKey":"PrizePool-200043026","platform":13,"app":-1,"h5Fingerprint":"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"}""",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.103 Safari/537.36",
            "Content-Type": "application/json;charset=utf-8",
        },
        "cookies": {"token": token}
    }
    res = await req(**meta)
    if res:
        try:
            logger.info(res.text)
            if res.status_code != 200:
                result.update({"msg": f"mt {token} 领取失败！"})
                cache.delete(f'meituan_{token}')
            else:
                t = str(time_ns())
                meta.update({
                    "method": "POST",
                    "url": "https://promotion.waimai.meituan.com/playcenter/common/v1/doaction",
                    "params": {},
                    "data": {},
                    "json": {
                        "activityViewId": "jXL-9iEaRTsv-FZdpX4Z4g",
                        "actionCode": 1000,
                        "lat": 23.16397476196289,
                        "lng": 113.40444946289062,
                        "gdId": 422324,
                        "instanceId": f'{t[:14]}.{t[14:].zfill(16)}',
                        "fpPlatform": 13,
                        "utmSource": "",
                        "utmCampaign": "",
                    }
                })
                res = await req(**meta)
                if res:
                    logger.info(res.text)
                result.update({"msg": f"mt {token} 签到成功！"})
        except Exception as e:
            result.update({"msg": f"mt {token} 签到程序异常"})
    # 钉钉通知
    await dingAlert(**result)


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
            "x-requested-with": "XMLHttpRequest",
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.42(0x18002a2a) NetType/4G Language/zh_CN",
            "login-check": "1",
            "Cookie": f"SESSION_TOKEN={token}",
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
            logger.info(f'app 签到 {res.text}')

            # # 补签
            # meta.update({
            #     "url": "https://wx.10086.cn/qwhdhub/api/mark/mark31/redomark",
            # })
            # res = await req(**meta)
            # logger.info(f'app 补签{res.text}')

            # 任务列表
            meta.update({
                "url": "https://wx.10086.cn/qwhdhub/api/mark/task/taskList",
                "json": {},
            })
            res = await req(**meta)
            print(res.text)
            for t in res.json()["data"]["tasks"]:
                taskName, taskId, taskType, jumpUrl = t["taskName"], t["taskId"], t["taskCategory"], t["jumpUrl"]

                # 任务详情
                meta.update({
                    "method": "POST",
                    "url": "https://wx.10086.cn/qwhdhub/api/mark/task/taskInfo",
                    "json": {"taskId": str(taskId)},
                })
                res = await req(**meta)
                logger.info(f'taskInfo {taskName} {taskType} {taskId} {res.text}')

                taskType = res.json()["data"]["taskType"]

                # if jumpUrl.isalnum():
                #     meta.update({
                #         "url": "https://wx.10086.cn/qwhdhub/api/mark/mark31/isMark31",
                #         "headers": {
                #             "Referer": f'{res.json()["data"]["backUrl"]}?function={taskId}&completeTaskId={taskType}'
                #         }
                #     })
                #     res = await req(**meta)
                #     print(res.text)

                # # 公众号任务 获取回调地址 （需要sid）
                # meta.update({
                #     "method": "POST",
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

    except Exception as e:
        logger.error(f'10086 {token} 签到程序异常:{e}')
        cache.delete(f'10086_{token}')

    await dingAlert(**result)


# 中国联通
async def m10010(**kwargs):
    result = {
        "code": 400,
        "msg": f'请输入ecs_token',
        "time": int(time())
    }
    token = kwargs.get("token", "")
    if not token:
        return result
    cache.set(f'10010_{token}', token)
    # 签到
    meta = {
        "method": "POST",
        "url": "https://act.10010.com/SigninApp/signin/daySign",
        "json": {
            "shareCl": "",
            "shareCode": ""
        },
        "headers": {
            "Cookie": f"ecs_token={token}"
        },
    }
    res = await req(**meta)
    try:
        if res.status_code == 200:
            logger.info(f'10010 daySign {res.text}')
            res = res.json()
            if res["status"] == "0001":
                cache.delete(f"10010_{token}")
                result.update({"code": 200, "msg": f'10010用户：{token} 检查token是否有效'})
                return result
            result.update({"msg": f'10010 {res["msg"]}'})
            # 任务
            meta.update({
                "url": "https://act.10010.com/SigninApp/superSimpleTask/getTask",
            })
            res = await req(**meta)
            for r in res.json()["data"]:
                for t in r["taskMsg"]:
                    # print(t)
                    if t["achieve"] == '0':
                        # meta.update({
                        #     "url": "https://act.10010.com/SigninApp/task/doTask",
                        #     "json": {
                        #         "id": "eda7a0714642495f9ffd9fe16be1c57a",
                        #         # "orderId": "6750f3ae1e79489289ad4e1a08b0fa66",
                        #         # "imei": "FBE7973D-8368-465C-AF0A-AA979110ECC2",
                        #         # "prizeType": "nq",
                        #         "positionFlag": "3"
                        #     }
                        # })
                        meta.update({
                            "url": "https://act.10010.com/SigninApp/simplyDotask/accomplishDotask",
                            "json": {
                                "actId": t.get("actId", ""),
                                "taskId": t.get("taskId", ""),
                                "systemCode": "QDQD",
                                "orderId": "",
                                "taskName": t.get("title", ""),
                                "taskType": t.get("taskType", "2")
                            }
                        })
                        res = await req(**meta)
                        meta.update({
                            "url": "https://act.10010.com/SigninApp/simplyDotask/doTaskS",
                            "json": {
                                "actId": t.get("actId", ""),
                                "taskId": t.get("taskId", ""),
                                # "taskType": "2",
                                "taskType": t.get("taskType", "2"),
                            },
                        })
                        res = await req(**meta)
                        logger.info(f'{r["id"]} {res.text}')
    except Exception as e:
        logger.error(f'10010 签到程序异常:{e}')
        cache.delete(f"10010_{token}")
        result.update({"msg": f"10010 签到程序异常"})
    # 钉钉通知
    await dingAlert(**result)
    return result


# 有赞(东鹏特饮)
async def youzan_dp(**kwargs):
    result = {
        "code": 400,
        "msg": f'请输入sid',
        "time": int(time())
    }
    token = kwargs.get("token", "")
    if not token:
        return result
    cache.set(f'dp_{token}', token)
    # 签到
    meta = {
        "url": "https://h5.youzan.com/wscump/checkin/checkinV2.json",
        "params": {
            "checkinId": "3124",
            # "app_id": "wxbe8abd76a650b858",
            # "kdt_id": "15131322",
            # "access_token": ""
        },
        "headers": {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.42(0x18002a2b) NetType/4G Language/zh_CN",
            "Extra-Data": '{"is_weapp":1,"sid":"%s","version":"2.151.5","client":"weapp","bizEnv":"wsc","uuid":""}' % token
        }
    }
    res = await req(**meta)
    try:
        if res.status_code == 200:
            logger.info(f'东鹏 checkin {res.text}')
            res = res.json()
            result.update({"msg": f'dp {res["msg"]}'})
            if res["code"] == -1:
                cache.delete(f"dp_{token}")
    except Exception as e:
        logger.error(f'dp 签到程序异常:{e}')
        cache.delete(f"dp_{token}")
        result.update({"msg": f"dp {token} 签到程序异常"})
        # 钉钉通知
    await dingAlert(**result)


# 闪惠
async def m95516(**kwargs):
    result = {
        "code": 400,
        "msg": f'请输入Authorization',
        "time": int(time())
    }
    token = kwargs.get("token", "")
    if not token:
        return result
    cache.set(f'95516_{token}', token)
    # 签到
    meta = {
        "method": "POST",
        "url": "https://youhui.95516.com/newsign/api/daily_sign_in",
        "json": {"date": datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ")},
        "headers": {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.42(0x18002a2b) NetType/4G Language/zh_CN",
            "Referer": "https://youhui.95516.com/newsign/public/app/index.html",
            "Authorization": token if token.startswith("Bearer") else f"Bearer {token}"
        }
    }
    res = await req(**meta)
    try:
        if res and res.status_code == 200:
            logger.info(f'95516 daily_sign_in {res.text}')
            result.update({"msg": f'95516 签到成功！'})
        else:
            logger.error(f'95516 {res.text}')
            result.update({"msg": f'95516 {token} {res.json().get("message", "")}'})
            if res.status_code == 401:
                cache.delete(f"95516_{token}")
    except:
        logger.error(f'95516 签到程序异常:{e}')
        cache.delete(f"95516_{token}")
        result.update({"msg": f"95516 {token} 签到程序异常"})

    # 钉钉通知
    await dingAlert(**result)


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

    pre_list = ['jd', 'csai', 'sichuanair', 'dragon_boat_2023', 'meituan', 'weimob', '10086', '10010', 'dp']

    for k, v in os.environ.items():
        if k.lower() in pre_list:
            for v_ in v.split(";"):
                cache.set(f'{k.lower()}_{v_}', v_)
             
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
    # 10010
    tasks += [asyncio.create_task(m10010(**{"token": cache[k]})) for k in cache.iterkeys() if k.startswith("10010_")]
    # 东鹏特饮
    tasks += [asyncio.create_task(youzan_dp(**{"token": cache[k]})) for k in cache.iterkeys() if k.startswith("dp_")]
    # 95516
    tasks += [asyncio.create_task(m95516(**{"token": cache[k]})) for k in cache.iterkeys() if k.startswith("95516_")]
 
    result_list = await asyncio.gather(*tasks)
    # logger.info(result_list)
    return result_list


if __name__ == '__main__':
    # import uvicorn
    # uvicorn.run(app, host="0.0.0.0", port=8082)
    asyncio.run(crontab_task())
