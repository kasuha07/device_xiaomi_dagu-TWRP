# TWRP for Xiaomi Pad 5 Pro 12.4 · dagu

[![Release CI](https://github.com/kasuha07/device_xiaomi_elish-TWRP/actions/workflows/release.yml/badge.svg?branch=dagu-miui14-android13)](https://github.com/kasuha07/device_xiaomi_elish-TWRP/actions/workflows/release.yml)

面向小米平板 5 Pro 12.4（`dagu`）的非官方 TWRP 设备树，适配 **MIUI Pad 14 / Android 13**。默认分支为 `dagu-miui14-android13`，当前设备版本为 `MIUI14-A13-r3`。

- [下载 Release](https://github.com/kasuha07/device_xiaomi_elish-TWRP/releases)
- [构建与发布记录](https://github.com/kasuha07/device_xiaomi_elish-TWRP/actions/workflows/release.yml)
- [适配依据、解密修正与日志采集](docs/dagu-miui14.md)

## 兼容性与验证

目标硬件是 **dagu**。目前收到的实机反馈来自 `MIUI Pad 14.0.6.0(TMHCNXM)` Android 13 移植 ROM；该版本号不是 dagu 原厂 ROM 标识。

| 项目 | 当前结果 |
| --- | --- |
| 启动并进入 TWRP | 已收到实机日志 |
| `/data` metadata 解密 | 日志确认成功 |
| 原锁屏图案解密 | 用户初步反馈 r3 可正常解密 |
| 备份恢复、MTP、刷入完整 ROM | 尚未完成验证 |

r3 为高通 QSEE 安全存储建立 `/mnt/vendor/persist -> /persist`，并在密码验证前挂载 persist，修正此前输入图案后解密一直转圈的问题；同时修正固件分区的挂载参数。保留现有 FBE / metadata 加密参数，无需格式化数据。

本分支基于 TWRP Android 12.1 源码体系构建，报告的平台版本为 Android 13。设备树保留 elish、enuma、pipa 的构建入口；本分支的 Release CI 只构建 dagu，其他机型的说明见[上游仓库](https://github.com/ymdzq/device_xiaomi_elish-TWRP)。

## 下载与使用

从[本仓库 Releases](https://github.com/kasuha07/device_xiaomi_elish-TWRP/releases) 下载 `boot.img` 和 `SHA256SUMS`。尚未发布版本时，可以在成功的 Actions 运行中下载构建产物。

Linux 下可在下载目录校验：

```bash
sha256sum --ignore-missing -c SHA256SUMS
```

使用 [Android Platform Tools](https://developer.android.com/tools/releases/platform-tools)，将设备重启到 fastboot 后先临时启动：

```bash
fastboot boot boot.img
```

进入 TWRP 后输入原锁屏图案，检查内部存储和 `/data/media/0`。**不要使用 `fastboot flash boot boot.img` 刷入这个完整镜像**：该镜像用于启动 recovery，直接替换 boot 会影响正常启动系统。

需要固化时，在验证临时启动可用后使用 TWRP 的“高级 → 刷入当前的 TWRP”，或“安装 recovery ramdisk”功能。安装会修改 boot ramdisk；使用 Magisk 的设备可能需要重新修补 root。

## Release CI

工作流使用 `ci/manifest.xml` 固定 TWRP 各源码仓库的提交，来自 r3 已编译验证的源码快照。设备树取自触发工作流的本仓库提交，不再从上游克隆可能变化的分支。

两种使用方式：

1. **手动构建**：进入 [Actions → Dagu Release](https://github.com/kasuha07/device_xiaomi_elish-TWRP/actions/workflows/release.yml)，选择 `dagu-miui14-android13` 并运行。`release_tag` 留空时只上传 Actions 产物；填写 `dagu-miui14-a13-…` 标签时创建 Release，可通过 `prerelease` 选择预发布。
2. **标签发布**：向本仓库推送 `dagu-miui14-a13-*` 标签，自动构建该标签对应提交并创建正式 Release。例如：

```bash
git tag dagu-miui14-a13-r3
git push github dagu-miui14-a13-r3
```

镜像通过设备标识、版本、分区大小、Keymaster、persist 解密挂载配置、内核与模块匹配及 AVB 哈希检查后才会发布。产物包含 `boot.img`、`SHA256SUMS`、`build-info.json`、`manifest.xml` 和构建日志。自动构建不会替代实机验证。

发布使用 GitHub Actions 自带的 `GITHUB_TOKEN`，无需另外添加 PAT secret。仓库需要启用 Actions；工作流为发布任务声明 `contents: write`。

## 本地构建

在 Linux 上安装 Android 构建依赖和 [repo](https://source.android.com/docs/setup/reference/repo)。使用与 CI 一致的源码快照：

```bash
mkdir -p ~/twrp-dagu
cd ~/twrp-dagu
repo init --depth=1 \
  -u https://github.com/kasuha07/device_xiaomi_elish-TWRP.git \
  -b dagu-miui14-android13 -m ci/manifest.xml
repo sync -c --no-clone-bundle --no-tags -j4
git clone --branch dagu-miui14-android13 \
  https://github.com/kasuha07/device_xiaomi_elish-TWRP.git device/xiaomi/elish
export ALLOW_MISSING_DEPENDENCIES=true
source build/envsetup.sh
lunch twrp_dagu-eng
mka adbd bootimage -j"$(nproc)"
```

输出为 `out/target/product/elish/boot.img`。`elish` 是公共设备树的输出目录名，`twrp_dagu-eng` 决定构建 dagu 镜像。构建中的 Magisk 打包步骤需要网络。

## 致谢

- [上游 TWRP 设备树 · ymdzq](https://github.com/ymdzq/device_xiaomi_elish-TWRP)
- [小米平板 5 Pro OrangeFox 设备树](https://github.com/ymdzq/OFRP-device_xiaomi_elish)
- [sekaiacg / skkk](https://github.com/sekaiacg/device_xiaomi_alioth-TWRP)
- [TeamWin](https://github.com/TeamWin)、本次使用的 [SK_Recovery](https://github.com/ymdzq/SK_Recovery) 及各依赖仓库贡献者
