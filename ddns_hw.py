import asyncio
from huaweicloudsdkcore.auth.credentials import BasicCredentials
from huaweicloudsdkdns.v2 import *
from huaweicloudsdkdns.v2.region.dns_region import DnsRegion
from httpx import AsyncClient
from user_agent import generate_user_agent
from json import dumps
import pandas as pd
from loguru import logger
from argparse import ArgumentParser

parser = ArgumentParser(description="华为DDns,设置优选IP")

parser.add_argument_group()
parser.add_argument("--ak", default="", help="access key")
parser.add_argument("--sk", default="", help="secret key")
parser.add_argument("--name", default="", help="域名")
parser.add_argument("--prefix", default="", help="域名前缀(非必填)")
parser.add_argument("--type_", default="", help="类型(非必填,默认A)")
parser.add_argument("--records", default=[], help="IP列表(非必填)")
parser.add_argument("--ttl", default=[], help="TTL(非必填)")
parser.add_argument("--weight", default=1, help="权重(非必填，默认1)")
parser.add_argument("--weight", default=1, help="权重(非必填，默认1)")
parser.add_argument("--zone_id", default="", help="zone_id(非必填，移除记录需要)")
parser.add_argument("--remove", default=0, help="移除记录(非必填，默认0)")


# 请求函数
async def req(**kwargs):
    url = kwargs.get("url", "")
    if not url: return None
    headers = {"User-Agent": generate_user_agent()} | kwargs.get("headers", {})
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
        logger.error(f'请求错误：{url} {e}')
        retry = kwargs.get("retry", 0)
        retry += 1
        if retry > 2:
            return None
        return await req(**kwargs | {"retry": retry})


# 获取优质IP
async def get_optimization_ip(**kwargs):
    meta = {
        "method": "POST",
        "url": "https://api.hostmonit.com/get_optimization_ip",
        "data": dumps({"key": "iDetkOys"}),
    }
    res = await req(**meta)
    # print(res.text)
    res = res.json()
    df = pd.DataFrame(res["info"])
    df = df.sort_values(by=["latency"], ascending=False)
    df.sort_index().head()
    # print(df)
    # res = {"code": 200, "info": {v[3]: v[1] for v in df.values}}
    # print(res)
    records = [v[1] for v in df.values][::-1]
    # print(records)
    return records


# 设置DNS
async def set_dns(**kwargs):
    ak = kwargs.get("ak", "")
    sk = kwargs.get("sk", "")
    region = kwargs.get("region", "cn-east-3")  # https://developer.huaweicloud.com/endpoint
    name = f'{kwargs.get("name", "")}.'
    prefix = kwargs.get("prefix", "")
    if prefix != "@":
        name = f'{prefix}.{kwargs["name"]}.'.lstrip(".")
    if not all([ak, sk, name]):
        logger.error(f'缺少必要参数 access key、secret key、name')
        return None
    type_ = kwargs.get("type", "A")
    records = kwargs.get("records", [])
    ttl = kwargs.get("ttl", "600")
    weight = kwargs.get("weight", 1)
    zone_id = kwargs.get("zone_id", "")
    remove = kwargs.get("remove", False)

    client = DnsClient.new_builder().with_credentials(BasicCredentials(ak, sk)).with_region(
        DnsRegion.value_of(region)).build()

    # 查询记录
    request = ListRecordSetsWithLineRequest()
    # request.limit = kwargs.get("limit", 100)
    request.type = type_
    request.name = name

    res = client.list_record_sets_with_line(request)
    if res.recordsets:
        for r in res.recordsets:
            # 更新记录
            request = UpdateRecordSetRequest()
            request.zone_id = r["zone_id"]
            request.recordset_id = r["id"]
            request.body = UpdateRecordSetReq(name=name, type=type_, ttl=ttl, records=records)
            response = client.update_record_set(request)
            logger.info(f'{name} 更新：{response}')
            if remove:
                # 删除记录
                request = DeleteRecordSetsRequest()
                request.zone_id = r["zone_id"]
                request.recordset_id = r["id"]
                response = client.delete_record_sets(request)
                logger.info(f'{name} 删除：{response}')
    else:
        if zone_id:
            # 创建记录
            request = CreateRecordSetWithLineRequest()
            request.zone_id = zone_id
            request.body = CreateRecordSetWithLineReq(type=type_, name=name, ttl=ttl, weight=weight, records=records)
            response = client.create_record_set_with_line(request)
            logger.info(f'{name} 创建：{response}')
        else:
            # 获取zone_id
            request = ListPublicZonesRequest()
            response = client.list_public_zones(request)
            if response.zones:
                for r in response.zones:
                    # 创建记录
                    request = CreateRecordSetWithLineRequest()
                    request.zone_id = r["id"]
                    request.body = CreateRecordSetWithLineReq(type=type_, name=name, ttl=ttl, weight=weight,
                                                              records=records)
                    response = client.create_record_set_with_line(request)
                    logger.info(f'{name} 创建：{response}')
            else:
                logger.error(f'{name} 未查到zone_id!')


async def main():
    args = parser.parse_args()
    args = args.__dict__
    # 此处填写或终端输入
    meta = {
        "ak": "",
        "sk": "",
        "name": "",  # 域名
        "prefix": "",  # 前缀，
        "records": await get_optimization_ip()
    }
    meta.update(args)
    await set_dns(**meta)


if __name__ == '__main__':
    asyncio.run(main())
