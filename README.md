# Sign
签到啦

(目前支持京东京豆、南航、川航、携程、微信支付有优惠小程序龙舟游戏刷免费提现券、美团优惠券、统一快乐星球、中国移动、中国联通、东鹏特饮、云闪付、卡亨星球、鸿星尔克、迪卡侬、萤石、掘金、途虎养车、爱奇艺)

[使用教程](https://www.1itre.link/2024/02/21/%E6%AF%8F%E6%97%A5%E7%AD%BE%E5%88%B0/)

```bash
pip install uvicorn fastapi websockets httpx loguru diskcache apscheduler SQLAlchemy python-dateutil -i https://pypi.tuna.tsinghua.edu.cn/simple
```

运行项目（两种方式运行: 第一种直接运行脚本;第二种启动服务后通过接口添加token设置定时任务）

第一种：直接运行脚本

```bash
python sign.py
```

追加参数

```bash
python sign.py --pt_pin jd_XXX --pt_key AAJXXX
```

第二种：启动服务(服务可用于添加token和设置定时任务)

```bash
uvicorn sign:app --host 0.0.0.0 --port 8081
```

访问 [http://127.0.0.1:8081/docs](http://127.0.0.1:8081/docs) 通过接口添加账户token等

#### 开发描述
程序主要使用fastapi开发的接口，请求库主要使用httpx，定时调度器使用的是apschedule，数据库使用的是sqlite，缓存使用的是diskcache,调度器和缓存是共用同一个sqlite数据库，使用sqlite数据库主要是减少环境依赖和方便，也方便的查看任务执行情况。当然也可以换成其它数据库，修改一些脚本数据库配置即可。

接口可以方面添加token等令牌信息，之后的定时运行可以使用apschedule定时调度运行(默认早上九点签到),也可使用crontab运行脚本。

crontab运行脚本后面添加参数即可(例如 0 9 * * * ~/python3 ~/sign.py --pt_pin jd_XXX --pt_key AAJXXX)。

签到状态提醒目前只写了钉钉通知，修改脚本的dingAlert函数中的access_token和secret即可。

后续也会增加其它平台...

脚本运行命令设置选项  

```
Options:
  --pt_pin       [/signBeanAct]京东Cookie中获取pt_pin值
  --pt_key       [/signBeanAct]京东Cookie中获取pt_key值
  --csai         [/csairSign]南航账户Cookie中sign_user_token值
  --sichuanair   [/sichuanairSign]川航账户Cookie中access-token值
  --ctrip        [/ctripSign]携程账户Cookie中cticket值
  --meituan      [/meituan]美团账户Cookie中token值
  --weimob       [/weimob]统一快乐星球账户Cookie中X-WX-Token值
  --10086        [/10086]中国移动账户Cookie中SESSION_TOKEN值
  --10010        [/10010]中国联通账户Cookie中ecs_token值
  --dp           [/dp]东鹏账户header中sid值
  --95516        [/95516]云闪付账户header中Authorization值
  --kraf         [/kraf]卡亨星球账户header中token值
  --erke         [/erke]鸿星尔克账户的memberId值
  --honda        [/honda]本田账户的Authori-zation值
  --decathlon    [/decathlon]迪卡侬账户的Authorization值
  --ys           [/ys]萤石账户的sessionid值
  --juejin       [/juejin]掘金账户的sessionid值
  --tuhu         [/tuhu]途虎养车账户的Authorization值

```

说明：  

京东`--pt_pin`pt_pin和`--pt_key`需同时传入！脚本也支持使用青龙面板运行，追加的参数设置为环境变量即可。

## 常见问题

### 关于 令牌 获取
可以使用抓包工具，例如Fiddler、Wireshark，或者浏览器插件，或者使用浏览器自带的开发者工具，例如Chrome的开发者工具。
手机抓包可以设置代理去抓包（需安装证书才可以抓取https协议请求），也可以使用app去抓包，苹果用户推荐使用Stream,安卓用户推荐使用HttpCanary。

### 青龙面板支持
程序也是支持了青龙面板，令牌通过环境变量传入即可。

### 关于 docs 空白页面
由于fastapi的docs使用的是swagger-ui的远程静态文件，远程静态文件偶尔会加载一程，所以docs出现空白页面，不影响接口使用。


## 阶段计划
- 添加Cookie签到（解决多参数认证）
- 加入任务灵活配置页面
- 重新编写部署教程，添加视频教程


## 总结
由于这是本人业余时间开发的项目，可能还有很多问题不能及时解决（也会抽时间解决），这个项目也可能存在很多不尽如人意的地方，在细节方面我也会尽力地去修改，也欢迎大家提出自己的问题，以及项目的相关建议，也欢迎大家提交代码。如果觉得这个主题不错，欢迎大家去使用。当然了，如果能[赞赏](https://ko-fi.com/litre)我一下，我也是不介意的。(●ˇ∀ˇ●)  

<img src=https://github.com/Litre-WU/Sign/blob/master/wechat.jpg width=150/>

这个项目对于部分人群可能无法灵活配置，后续抽时间开发web版和app去让各类用户方便使用，欢迎大家修改，也希望这个项目越来越多的人能够喜欢。  
