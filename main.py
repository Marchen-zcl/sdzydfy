import asyncio
import os
# noinspection PyUnresolvedReferences
from playwright.async_api import async_playwright, expect
from loader import Loader
from datetime import datetime

user = ""  # 账号
psw = ""  # 密码
lapse_snap = 600
lapse_night = 120000
lapse_common = 30000
timeout_time = 3000
retry = 30
retry_times = 0
scheduleUrl = None
orderUrl = None
preUrl = None
time = None
preTime = None
appointment_type = None
docName = None
orderInfo = None



def checkConfig():
    # 检查文件是否存在
    global user, psw, lapse_snap, lapse_night, lapse_common, retry, timeout_time, appointment_type, docName
    if not os.path.exists("config.txt"):
        # 如果文件不存在，创建文件并写入默认内容,并提示用户（黄色）
        print("\033[33m未找到配置文件，已在同级目录创建默认配置文件config.txt！\033[0m")
        with open("config.txt", "w", encoding="utf-8") as file:
            file.write(
                "user =   # 账号\n"
                "psw =   # 密码\n"
                "lapse_snap = 600  #抢号时间间隔(耗秒) 不建议低于500ms\n"
                "lapse_night = 120000  #夜间停挂刷新间隔(毫秒) 必须为1000整数倍 不建议高于300000ms\n"
                "lapse_common = 30000  #捡漏时间间隔(毫秒) 不建议低于10000ms\n"
                "retry = 30  #抢号失败重试次数\n"
                "timeout_time = 3000  #超时时间(毫秒)\n"
                "appointment_type =  #预约类型(1专家，2普通)\n"
                "docName =  #医生姓名\n"
            )
    else:
        # 如果文件存在，读取内容并更新全局字典
        with open("config.txt", "r", encoding="utf-8") as file:
            for line in file:
                # 忽略注释行
                if "#" in line:
                    line = line[: line.index("#")]
                # 分割键和值
                parts = line.split("=")
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip()
                    match (key):
                        case "user":
                            user = value
                        case "psw":
                            psw = value
                        case "lapse_snap":
                            lapse_snap = int(value)
                        case "lapse_night":
                            lapse_night = int(value)
                        case "lapse_common":
                            lapse_common = int(value)
                        case "retry":
                            retry = int(value)
                        case "timeout_time":
                            timeout_time = int(value)
                        case "appointment_type":
                            appointment_type = value
                        case "docName":
                            docName = value
    expect.set_options(timeout=timeout_time)

def saveUser(username, password):
    with open("config.txt", "r", encoding="utf-8") as file:
        lines = file.readlines()
    with open("config.txt", "w", encoding="utf-8") as file:
        for line in lines:
            if "user" in line:
                file.write(f"user = {username}  # 账号\n")
            elif "psw" in line:
                file.write(f"psw = {password}  # 密码\n")
            else:
                file.write(line)
        print("\r\033[32m账号密码已保存！可在config.txt中修改或删除配置文件重置\033[0m")


def getTime():
    now = datetime.now()
    if now.hour < 6 or (now.hour == 6 and now.minute < 59 and now.second < 50):
        return -1
    elif (now.hour == 7 and now.minute < 10) or (
        now.hour == 6 and now.minute == 59 and now.second >= 30
    ):
        return 1
    else:
        return 0


async def handle_dialog(dialog, page,context):
    print(f"\n\033[33m网页弹出警告: {dialog.message}\033[0m")
    if dialog.message=="用户登录已超时,请重新登录":
        page_new=await context.new_page()
        await page_new.goto("https://pdjh.sdzydfy.com/login_info.aspx")
        await page_new.locator("#tbName").fill(user)
        await page_new.locator("#txt_password").fill(psw)
        await page_new.get_by_role("button", name="登 录").click()
        await page_new.wait_for_load_state(state="load")
        await page_new.close()
    await dialog.accept()
    await page.go_back()


async def handle_url_change(frame, page):
    global scheduleUrl, orderUrl, preUrl, time
    if frame.url == "https://pdjh.sdzydfy.com/newPages/sxError.htm":
        print("\r\033[33m刷新速度过快！抢票间隔+100ms\033[0m")
        await page.wait_for_load_state(state="load", timeout=time)
        if time is not None:
            time += 100
        if orderUrl is not None:
            await page.goto(orderUrl, timeout=time)
        elif scheduleUrl is not None:
            await page.goto(scheduleUrl, timeout=time)
        else:
            await page.goto(preUrl,timeout=time)
    if "Select_Date.aspx" in frame.url:
        scheduleUrl = frame.url
    if "Fill_info.aspx" in frame.url:
        orderUrl = frame.url
    preUrl = frame.url


async def getRow(page):
    link1 = await page.locator(
            "#GridView1 > tbody > tr:nth-child(2)>td:nth-child(2)"
        ).text_content(timeout=time)!=""


    link2 = (
        await page.locator(
            "#GridView1 > tbody > tr:nth-child(3)>td:nth-child(2)"
        ).text_content(timeout=time)
        != ""
    )
    if link1:
        return 2
    elif link2:
        return 3
    else:
        return -1


async def launchChrome(playwright):
    browser = await playwright.chromium.launch(headless=False)
    context = await browser.new_context()
    page = await context.new_page()
    page.on("framenavigated", lambda frame: handle_url_change(frame, page))
    page.on("dialog", lambda dialog: handle_dialog(dialog, page,context))
    await inputMsg(browser, page)


async def inputMsg(browser, page):
    try:
        await page.goto("https://pdjh.sdzydfy.com/login_info.aspx")
        while 1:
            username = user or input("请输入用户名：")
            password = psw or input("请输入密码：")
            if await login(page, browser, username, password):
                break
    except Exception as e:
        print("登录失败,正在重新尝试！")
        await page.wait_for_timeout(lapse_snap)
        await inputMsg(browser, page)


async def login(page, browser, username, password):
    global orderInfo,loader
    try:
        global appointment_type
        loader = Loader("正在尝试登录", "登录成功", 0.2).start()
        await page.locator("#tbName").fill(username,timeout=timeout_time)
        await page.locator("#txt_password").fill(password,timeout=timeout_time)
        await page.get_by_role("button", name="登 录").click()
        # 等待页面跳转
        await page.wait_for_load_state(state="load")
        content = await page.content()
        if "密码有误，请重新输入." in content or "没有该用户，请先注册" in content:
            print("\r", end="")
            print("\033[31m账号或密码有误，请重新输入！\033[0m")
            loader.stop(False)
            return False
        if user == "" or psw == "":
            saveUser(username, password)
        await expect(
            page.locator(
                "#Form1 > table > tbody > tr:nth-child(2) > td > table > tbody > tr:nth-child(3) > td > table > tbody > tr:nth-child(1) > td:nth-child(3) > table > tbody > tr:nth-child(1) > td:nth-child(1) > strong"
            )
        ).to_have_text("当前位置： 选择科室")
        loader.stop()
        while 1:
            # 选择预约类型
            AppointmentType =appointment_type or input("请选择预约类型：\n1.专家预约 \n2.普通预约\n")
            if AppointmentType == "1":
                appointment_type = AppointmentType
                break
            if AppointmentType == "2":
                appointment_type = AppointmentType
                await page.goto(
                    "https://pdjh.sdzydfy.com/newPages/Select_Dep.aspx?hos_id=xw&re_type=3"
                )
                await page.wait_for_load_state(state="load",timeout=timeout_time)
                break
            elif AppointmentType != "1" and AppointmentType != "2":
                print("输入错误，请重新输入！")
        while await chooseDoc(page, browser):
            pass

    except Exception as e:
        if hasattr(loader, 'stop'):
            loader.stop(False)
        # 按照年月日时分秒的格式输出当前时间
        print('\n',datetime.now().strftime('%H:%M:%S'),e)
        print("网络出错了，正在重新尝试！")
        if orderUrl is not None:
            await page.wait_for_timeout(lapse_snap)
            await page.goto(orderUrl,timeout=timeout_time)
            await page.wait_for_load_state(state="load", timeout=timeout_time)
            await postOrder(page, browser, orderInfo)
        elif scheduleUrl is not None:
            await page.wait_for_timeout(lapse_snap)
            await page.goto(scheduleUrl,timeout=timeout_time)
            await page.wait_for_load_state(state="load", timeout=timeout_time)
            await waiter(page, browser, orderInfo)
        else:
            await page.goto("https://pdjh.sdzydfy.com/login_info.aspx",timeout=timeout_time)


async def chooseDoc(page, browser):
    global docName
    DocName =docName or input("请输入医生姓名：")
    # 在页面中查找医生姓名
    doc_locator = page.locator(f'a:has-text("{DocName}")')
    if await doc_locator.count() == 0:
        print("\033[31m未找到医生，请重新输入！\033[0m")
        await page.reload(timeout=timeout_time)
        return 1
    else:
        docName = DocName
        if orderUrl is not None:
            await page.wait_for_timeout(lapse_snap)
            await page.goto(orderUrl,timeout=timeout_time)
            await page.wait_for_load_state(state="load", timeout=timeout_time)
            await postOrder(page, browser, orderInfo)
        elif scheduleUrl is not None:
            await page.wait_for_timeout(lapse_snap)
            await page.goto(scheduleUrl,timeout=timeout_time)
            await page.wait_for_load_state(state="load", timeout=timeout_time)
            await waiter(page, browser, orderInfo)
        else:
            await doc_locator.nth(0).click()
            await getSchedule(page, browser)


async def getSchedule(page, browser):
    global orderInfo
    th_content = await page.locator(
        "#GridView1 > tbody > tr:nth-child(1)"
    ).text_content()
    th_content = th_content.strip()
    dates = [th_content[i : i + 8] for i in range(0, len(th_content), 8)]
    td_content1 = await page.locator(
        "#GridView1 > tbody > tr:nth-child(2)>td"
    ).element_handles()
    td_content2 = await page.locator(
        "#GridView1 > tbody > tr:nth-child(3)>td"
    ).element_handles()
    schedules = {"上午": [], "下午": []}
    for e1 in td_content1:
        x = await e1.text_content()
        if x.strip() != "上午":
            schedules["上午"].append(x.strip())
    for e2 in td_content2:
        x = await e2.text_content()
        if x.strip() != "下午":
            schedules["下午"].append(x.strip())
    js = 1
    list = []
    for i in range(len(dates)):
        for key in schedules.keys():
            if (
                schedules[key][i] != ""
                and schedules[key][i] != "停诊"
                and "超时" not in schedules[key][i]
            ):
                list.append({"date": dates[i], "time": key})
                print(f"{js}. \033[36m{dates[i]} {key} ", end="")
                if "约满" in schedules[key][i]:
                    list[js - 1]["status"] = "0"
                    print(f"\033[31m {schedules[key][i]}\033[0m(可捡漏)")
                else:
                    list[js - 1]["status"] = "1"
                    print(f"\033[32m {schedules[key][i]}\033[0m")
                js += 1
    list.append({"date": "-1", "time": "-1", "status": "0"})
    print(f"{js}. \033[36m日程表后一天的号源（只能是后一天）\033[0m(可抢号)")
    chooseNo =input("请选择预约时间：")
    if chooseNo.isdigit():
        if int(chooseNo) > len(list) or int(chooseNo) < 1:
            print("\033[31m输入错误，重新输入\033[0m")
            await page.reload(timeout=timeout_time)
            await getSchedule(page, browser)
        orderInfo=list[int(chooseNo) - 1]
        await waiter(page, browser, orderInfo)
    else:
        print("\033[31m输入错误，重新输入\033[0m")
        await page.reload(timeout=timeout_time)
        await getSchedule(page, browser)

async def waiter(page, browser, info):
    try:
        global preTime, timeout_time
        times = 0
        while getTime() == -1:
            loader = Loader("当前时间不在捡漏预约抢号时间内，等待中", "到达预约时间！", 0.2, "\033[1;33m").start()
            await page.wait_for_timeout(1000)
            times += 1
            if times % (lapse_night / 1000) == 0:
                await page.reload(timeout=timeout_time)
            loader.stop(False)
        print(f"\r\033[92m当前在预约时间内！\033[0m")
        preTime = getTime()
        if info["status"] == "0":
            await snap(page, browser, info)
        elif info["status"] == "1":
            await register(page, browser, info)
    except Exception as e:
        print('\n',datetime.now().strftime('%H:%M:%S'),e)
        print("\033[1;33m出错了，正在重试!\033[0m")
        timeout_time+=1000
        await page.wait_for_timeout(time)
        await page.goto(scheduleUrl,timeout=timeout_time)
        await page.wait_for_load_state(state="load", timeout=timeout_time)
        await waiter(page, browser, info)


async def snap(page, browser, info):
    try:
        global time, retry_times, timeout_time
        if info["date"] != "-1":
            if getTime() == 1:
                if time is None:
                    time = lapse_snap
                print(f"\r\033[36m当前为抢号模式，{(time/1000)}秒刷新一次\033[0m")
            else:
                if time is None:
                    time = lapse_common
                print(f"\r\033[36m当前为捡漏模式，{time/1000}秒刷新一次\033[0m")
            # 在#GridView1 > tbody > tr:nth-child(1)选择器下，找到包含指定日期的th，并获取他是第几个th
            col_index = await page.locator("#GridView1 > tbody > tr:nth-child(1)").evaluate(
                f"(element) => Array.from(element.children).findIndex(e => e.innerText.replaceAll('\\n', '').includes(`{info['date']}`))",timeout=timeout_time
            )
            if info["time"] == "上午":
                row_index = 2
            else:
                row_index = 3
        else:
            times = 0
            while getTime() != 1:
                loader = Loader(
                    "当前时间不在抢号时间内，等待中（若要捡漏或预约已有排班，请重新启动选择已有排班）", "到达抢号时间！", 0.2, "\033[1;33m"
                ).start()
                await page.wait_for_timeout(1000)
                times += 1
                if times % (lapse_night / 1000) == 0:
                    await page.reload(timeout=timeout_time)
                loader.stop(False)
            print(f"\r\033[92m到达抢号时间！\033[0m")
            if time is None:
                time = lapse_snap
            print(f"\033[36m当前为抢号模式，{(time / 1000)}秒刷新一次\033[0m")
            col_index = 8
            row_index = None
        cs = 1
        while True:
            if row_index  is not None:
                link = page.locator(
                    f"#GridView1 > tbody > tr:nth-child({row_index}) > td:nth-child({col_index + 1}) > a"
                )
            else:
                tmp = await getRow(page)
                if tmp == -1:
                    loader = Loader(f"暂时无号，抢号尝试{cs}次...", "", 0.2, "\033[1;33m").start()
                    cs += 1
                    await page.wait_for_timeout(time)
                    loader.stop(False)
                    await page.reload(timeout=timeout_time)
                    if getTime() != preTime:
                        await waiter(page, browser, info)
                    continue
                else:
                    row_index = tmp
                    link = page.locator(
                        f"#GridView1 > tbody > tr:nth-child({row_index}) > td:nth-child({col_index + 1}) > a"
                    )
            if await link.is_visible(timeout=time):
                # await page.wait_for_timeout(time)
                await link.click()
                await page.wait_for_load_state(state="load", timeout=timeout_time)
                await postOrder(page, browser, info)
                break
            else:
                loader = Loader(f"暂时无号，抢号尝试{cs}次...", "", 0.2, "\033[1;33m").start()
                cs += 1
                await page.wait_for_timeout(time)
                loader.stop(False)
                await page.reload(timeout=timeout_time)
                if getTime() != preTime:
                    await waiter(page, browser, info)
    except Exception as e:
        print('\n',datetime.now().strftime('%H:%M:%S'),e)
        print("\033[1;33m出错了，正在重试!\033[0m")
        timeout_time+=1000
        await page.wait_for_timeout(time)
        await page.goto(scheduleUrl,timeout=timeout_time)
        await page.wait_for_load_state(state="load", timeout=timeout_time)
        await snap(page, browser, info)


async def postOrder(page, browser, info):
    try:
        global retry_times, time, timeout_time
        loader = Loader("检测到余号，正在尝试锁号", "抢号成功！", 0.2).start()
        check = page.locator('div>span[style*="color:Blue"]').nth(0)
        if await check.is_visible(timeout=time):
            await check.click()
            await page.wait_for_timeout(time)
            await page.locator("#btnConfirm").click()
            try:
                await expect(page.locator("#divTips")).to_contain_text("预约成功")
                loader.stop()
                input()
                await page.close()
                await browser.close()
                exit()
            except Exception as e:
                loader.stop(False)
                timeout_time += 1000
                if retry_times < retry:
                    print(f"\r\033[31m预约失败，正在重试第{retry_times + 1}次\033[0m")
                    retry_times += 1
                    await page.goto(orderUrl,timeout=timeout_time)
                    await page.wait_for_load_state(state="load", timeout=timeout_time)
                    await postOrder(page, browser, info)
                else:
                    print(f"\r\033[31m多次预约失败，请重新选择！\033[0m")
                    await page.goto(scheduleUrl,timeout=timeout_time)
                    await page.wait_for_load_state(state="load", timeout=timeout_time)
                    await getSchedule(page, browser)
        else:
            if retry_times < retry:
                print(f"\r\033[31m预约失败，正在重试第{retry_times+1}次\033[0m")
                retry_times += 1
                await page.goto(orderUrl,timeout=timeout_time)
                await page.wait_for_load_state(state="load", timeout=timeout_time)
                await postOrder(page, browser, info)
            else:
                print(f"\r\033[31m多次预约失败，请重新选择！\033[0m")
                await page.goto(scheduleUrl,timeout=timeout_time)
                await page.wait_for_load_state(state="load", timeout=timeout_time)
                await getSchedule(page, browser)
    except Exception as e:
        if hasattr(loader, 'stop'):
            loader.stop(False)
        timeout_time += 1000
        print('\n', datetime.now().strftime('%H:%M:%S'), e)
        print("\033[1;33m出错了，正在重试!\033[0m")
        await page.wait_for_timeout(time)
        await page.goto(orderUrl,timeout=timeout_time)
        await page.wait_for_load_state(state="load", timeout=timeout_time)
        await postOrder(page, browser, info)

async def register(page, browser, info):
    try:
        global timeout_time,time
        time=lapse_snap
        loader = Loader("正在跳转预约", "预约成功", 0.2).start()
        col_index = await page.locator("#GridView1 > tbody > tr:nth-child(1)").evaluate(
            f"(element) => Array.from(element.children).findIndex(e => e.innerText.replaceAll('\\n', '').includes(`{info['date']}`))",timeout=timeout_time
        )
        if info["time"] == "上午":
            row_index = 2
        else:
            row_index = 3
        await page.locator(
            f"#GridView1 > tbody > tr:nth-child({row_index}) > td:nth-child({col_index + 1}) > a"
        ).click()
        await page.wait_for_load_state(state="load", timeout=timeout_time)
        check = page.locator('div>span[style*="color:Blue"]').nth(0)
        if await check.is_visible(timeout=time):
            await page.wait_for_timeout(time)
            await check.click()
            await page.wait_for_timeout(time)
            await page.locator("#btnConfirm").click()
            try:
                await expect(page.locator("#divTips")).to_contain_text("预约成功")
                loader.stop()
                input()
                # 关闭浏览器
                await page.close()
                await browser.close()
                exit()
            except Exception as e:
                loader.stop(False)
                timeout_time += 1000
                print("\r\033[31m预约失败，请重新选择！\033[0m")
                await page.goto(scheduleUrl,timeout=timeout_time)
                await page.wait_for_load_state(state="load", timeout=timeout_time)
                await getSchedule(page, browser)
        else:
            loader.stop(False)
            print("\r\033[31m预约失败，请重新选择！\033[0m")
            await page.goto(scheduleUrl,timeout=timeout_time)
            await page.wait_for_load_state(state="load", timeout=timeout_time)
            await getSchedule(page, browser)
    except Exception as e:
        if hasattr(loader, 'stop'):
            loader.stop(False)
        timeout_time += 1000
        print('\n', datetime.now().strftime('%H:%M:%S'), e)
        print("\033[1;33m出错了，正在重试!\033[0m")
        await page.wait_for_timeout(time)
        await page.goto(scheduleUrl,timeout=timeout_time)
        await page.wait_for_load_state(state="load", timeout=timeout_time)
        await register(page, browser, info)

async def main():
    async with async_playwright() as playwright:
        checkConfig()
        await launchChrome(playwright)


asyncio.run(main())
