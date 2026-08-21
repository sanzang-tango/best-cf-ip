# best-cf-ips (ipv4)

## 项目功能

- 为多个公开或开源Cloudflare优选IP项目进行**聚合&去重&加地理标注&加国旗Unicode**，每3小时更新。  
- 可接入 [edgetunnel](https://github.com/cmliu/edgetunnel)-自定义订阅汇聚。  

<p align="center">
  <img src="src/IN-EDT.png" alt="效果图">
</p>

## API内容**示例**

- 更新日期以实际结果为准。
- **示例内容不要导入任何工具，请使用下方API。**

```txt
# 295 bestips updated at 2026-08-21 15:00
104.17.212.191:443#US 🇺🇸
104.25.0.8:443#US 🇺🇸
104.18.81.19:8443#US 🇺🇸
158.180.69.78:443#KR 🇰🇷
45.77.254.160:443#SG 🇸🇬
104.17.107.76:443#US 🇺🇸
75.2.79.84:443#US 🇺🇸
104.19.220.22:443#US 🇺🇸
2.27.109.144:443#HK 🇭🇰
104.24.0.8:443#US 🇺🇸
139.162.23.48:443#SG 🇸🇬
162.159.197.1:2053#US 🇺🇸
103.31.4.4:443#US 🇺🇸
207.148.119.176:443#SG 🇸🇬
104.17.0.8:443#US 🇺🇸
···
```

## 应用效果

- 经代理客户端解析后，节点名称将显示**国家代码**以及**国旗**。

<p align="center">
  <img src="src/good-job.png" alt="效果图">
</p>

### IP API

```
https://github.com/sanzang-tango/best-cf-ip/raw/refs/heads/main/best-cf-ipv4.txt
```
---

## 优选域名API，可配合IP API共同使用。非即时更新，视使用体验少量更新。

- 具体表现取决于使用者当地网络环境，仅供参考。

<p align="center">
  <img src="src/good-job2.png" alt="效果图">
</p>

### DOMAIN API

```
https://github.com/sanzang-tango/best-cf-ip/blob/main/best-cf-domain.txt
```

## 感谢以下个人或组织的公开的优选IP筛选数据

- [bestcf](https://bestcf.pages.dev)
- [WeTest](https://www.wetest.vip/page/cloudfront/address_v4.html)
- [UOUIN](https://api.uouin.com/cloudflare.html)
- Tiancheng
- [Mia](https://t.me/MiaChatChannel)
- [Gslege](https://github.com/gslege/CloudflareIP)
- [IPDB](https://ipdb.api.030101.xyz)
- [VPS789](https://vps789.com/cfip/?remarks=ip)
- [vvHan](https://cf.vvhan.com)
- s5公益
- Luoli

## 感谢以下开源项目

- [wp-statistics/GeoLite2-City](https://github.com/wp-statistics/GeoLite2-City) - 提供每周自动更新的 GeoLite2-City MMDB 数据库镜像。
- [MaxMind GeoLite2](https://www.maxmind.com) - IP 地理位置数据库原始数据提供方。
