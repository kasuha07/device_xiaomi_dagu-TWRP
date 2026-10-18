# dagu：MIUI Pad 14 / Android 13

此分支的目标硬件为小米平板 5 Pro 12.4（`dagu`），目标系统为 Android 13。用户提供的系统版本为 `MIUI Pad 14.0.6.0(TMHCNXM)`，并确认为移植 ROM。该版本号不能作为 dagu 原厂固件的标识，也不能据此选用移植来源机型的内核、DTB 或分区表。

## 配置依据

以小米官方 [dagu V14.0.11.0.TLZCNXM 完整 OTA](https://cdnorg.d.miui.com/V14.0.11.0.TLZCNXM/miui_DAGU_V14.0.11.0.TLZCNXM_4a23a11fd2_13.0.zip) 的 `boot.img`、`vendor_boot.img` 与 `vendor.img` 作为 Android 13 参数对照。提取结果已逐分区核对 OTA payload 中的 SHA-256。

| 项目 | dagu 配置 | 核对来源 |
| --- | --- | --- |
| 平台版本 | `13` | 原厂 `boot.img` 头与 `prop.default` |
| 首发 API | `31` | `ro.product.first_api_level` |
| 原厂 vendor VNDK | `30` | 原厂 `ro.vndk.version` |
| 启动镜像 | header v3、128 MiB、recovery-as-boot | 原厂 `boot.img` |
| userdata | F2FS、inlinecrypt | 原厂 `vendor_boot` 中的 `first_stage_ramdisk/fstab.qcom` |
| FBE | `aes-256-xts:aes-256-cts:v2+inlinecrypt_optimized+wrappedkey_v0` | 同上 |
| metadata 加密 | `aes-256-xts:wrappedkey_v0` | 同上 |
| metadata 密钥目录 | `/metadata/vold/metadata_encryption` | 同上 |
| Keymaster | `4.0` | 原厂 vendor VINTF manifest 与 `android.hardware.keymaster@4.0-service-qti.rc` |

`BoardConfig.mk` 和 `device.mk` 仅对 `PRODUCT_RELEASE_NAME=dagu` 应用 Android 13、F2FS、API 31 和 `PRODUCT_TARGET_VNDK_VERSION=30`，当前 TWRP 设备版本显示为 `MIUI14-A13-r3`。公共 fstab 的加密参数已与上述原厂参数核对；无需修改加密策略或格式化现有数据。

`PRODUCT_TARGET_VNDK_VERSION` 是此构建体系中内核模块 `vendor_overlay` 路径的目标版本，并不改变 recovery 自身的 VNDK。TWRP 源码仍为 Android 12.1，因此本次镜像内的 SDK 和 `ro.vndk.version` 均为 `32`；不应将这些源码对应属性强制改成原厂 vendor 的 `30`。

dagu 设置 `ro.twrp.keymaster=4.0`，等待 QSEE listeners 就绪后仅启动 Keymaster 4.0 与 Gatekeeper，避免同时启动两个 Keymaster 实现。额外的 Keymaster 4.1 VINTF 声明移到独立 ramdisk 目录，dagu 不打包该声明；其他产品仍加载它并保留原来的双服务启动方式。若移植 ROM 实际依赖其他版本的 Keymaster，需要依据其 vendor 和日志调整，不能保证本配置覆盖所有移植组合。

本分支沿用已有 `prebuilt/dagu/` 内核、DTB、DTBO 和 exfat 模块，其中内核来自上游提取的 dagu HyperOS 1.0.14.0，模块与该内核的 vermagic 一致。它们尚未在用户的移植 ROM 上验证。如果需要更换内核，应从适用于该设备的镜像提取，并同时核对配套模块，不能混用其他机型的预编译文件。

构建继续使用本仓库原先的 TWRP `android-12.1` 源码体系。这里的 `PLATFORM_VERSION=13` 是恢复环境报告的平台版本，不会把 Android 12.1 源码或 SDK 变成 Android 13。解密依赖原 README 提及的补丁或相应修改版 recovery；本次使用现有 `ymdzq/manifest_twrp:twrp-12.1` 构建环境验证。

移植 ROM 可能保留不同版本的 vendor、Keymaster 或加密策略，不能据 ROM 版本号判定这些组件。所用修改版 TWRP 会读取设备 vendor fstab 中的 `/data`、`/metadata` 条目，因此需要保留该能力（不要设置 `TW_SKIP_ADDITIONAL_FSTAB`）。

## 密码解密卡住的日志与修正

首版 `MIUI14-A13` 的实机日志显示，metadata 解密已成功，`/data` 通过 `/dev/block/dm-6` 挂载，用户 0 的密码类型识别为图案。输入密码后，日志停在 synthetic password 的 secdiscardable 分支；尚无用户 CE 解密成功记录。

同一时段 QSEE 的 `DrmLibFs` listener 连续报告 `mkdir(/mnt/vendor/persist)` 失败（`errno 13`）与 `file_open failed`，共约 3.1 万条。ramdisk 的 GP FS 配置指向 `/mnt/vendor/persist/data/`，但 recovery 将 persist 挂载到 `/persist`，没有建立对应路径。`r2` 在启动 QSEE 前创建 `/mnt/vendor/persist -> /persist`；`/mnt` 是 init 挂载的 tmpfs，因此该链接必须由 init 在运行时建立，不能仅放进 ramdisk。

内核还记录了 firmware、bluetooth 和 spunvm 挂载时的无效 SELinux context。`twrp.flags` 错将 fs_mgr 的 `wait` 写进 `fsflags`，且所用 vendor 专属标签不在当前 recovery 的 policy 中。`r2` 移除 `fsflags` 中的 `wait`，并将这三类 VFAT 挂载的 context 改为 recovery policy 中已有的 `u:object_r:vendor_file:s0`，保留读写模式与 UID/GID。此处修改仅作用于 recovery 自己的 fstab。

大量 `/data/data/…` 路径报红出现在输入密码前的目录大小扫描阶段，当时 CE 尚未解密；不能仅凭这些报错判断数据损坏。用户反馈 `r2` 的目录红字明显减少，但密码验证仍卡住。

`r2` 实机日志进一步确认：路径映射已存在，但密码验证卡住时 `/proc/mounts` 中没有 persist，`/persist` 是 rootfs 上的空目录。QSEE 的报错也从 `/mnt/vendor/persist` 变为 `/mnt/vendor/persist/data`（仍为 `errno 13`）。TWRP 只在读取时钟偏移或设置时临时挂载 persist，用完后会卸载；仅补上路径映射不足以支持密码验证。

`r3` 在 `/persist` 的 `twrp.flags` 条目添加 `mounttodecrypt`。当前 recovery 的 `TWPartitionManager::Decrypt_Device` 会在调用用户解密前挂载带此标志的分区，FBE 分支返回时保留该挂载。无需改变 persist 权限、创建空的安全存储目录或修改加密参数。用户初步反馈 `r3` 可正常解密；该反馈对应本文所述 dagu 与移植 ROM，尚未归档解密成功的日志。

## 构建

设备树仍放在 `device/xiaomi/elish`。`PRODUCT_DEVICE=elish` 是公共设备树的构建目录名；`PRODUCT_RELEASE_NAME=dagu` 决定使用 dagu 内核、模块和运行时设备标识。不要将输出目录误认为设备型号。

```bash
cd <TWRP 源码目录>
git clone --branch dagu-miui14-android13 https://github.com/kasuha07/device_xiaomi_elish-TWRP.git device/xiaomi/elish
source build/envsetup.sh
lunch twrp_dagu-eng
mka adbd bootimage
```

输出文件为 `out/target/product/elish/boot.img`。本仓库的 `Dagu Release` 工作流仅构建 `twrp_dagu`，产物目录仍为 `elish`；源码由 `ci/manifest.xml` 固定，设备树来自触发工作流的本仓库提交。手动构建和标签发布方法见 [README](../README.md#release-ci)。

原有 Magisk 打包步骤需要下载并校验预编译包。本分支已在 `BoardConfig.mk` 中声明 `BUILD_BROKEN_USES_NETWORK := true`，无需再对构建副本单独打补丁；该步骤仍需要可访问下载源的网络。

## 本次验证

`twrp_dagu-eng` 的 `adbd bootimage` 构建通过。已解包最终镜像，核对 header v3、128 MiB 大小、Android 13 平台标识、dagu 属性、首发 API 31、Keymaster 4.0 声明、fstab、设备版本字符串，以及内核和 exfat 模块的版本匹配；AVB footer 与镜像 SHA-256 哈希校验通过。其他三个产品的 Make 配置分支和 recovery XML 静态检查通过，未进行其他产品的完整构建。

`r2` 增量构建及最终镜像检查通过：确认 persist 路径映射在启动 QSEE 前建立，挂载标签通过镜像内 SELinux policy 校验，`/data`、`/metadata` 条目与首版完全相同。

`r3` 增量构建及最终镜像检查通过，新增核对打包后的 `/persist` 条目含 `mounttodecrypt`，并检查本次 recovery 源码中先挂载、后验证密码的调用顺序。镜像 AVB footer 与 SHA-256 哈希校验通过。

首版和 `r2` 已有实机启动与解密日志，确认 metadata 解密成功，但锁屏密码解密卡住。`r2` 的挂载信息用于定位上述 persist 未挂载的问题；用户已初步反馈 `r3` 可正常解密。

## 实机验证

先用临时启动验证，沿用本仓库的安装方式：

```bash
fastboot boot out/target/product/elish/boot.img
```

不要将这个完整镜像直接 flash 到 boot 分区。确认触摸、显示、ADB、MTP 和 `/data/media/0` 正常后，再按主 README 的“刷入当前的 TWRP”方式安装。编译通过或镜像校验通过不能替代实机解密测试。

需要在原有锁屏密码不变的情况下验证解密。若失败，保留数据并采集以下只读信息；其中密码、PIN 或解密密钥不应写入日志：

```bash
adb pull /tmp/recovery.log
adb logcat -b all -d > dagu-recovery-logcat.txt
adb shell getprop > dagu-recovery-properties.txt
adb shell 'ls -ld /mnt/vendor /mnt/vendor/persist /persist' > dagu-persist-paths.txt
adb shell 'cat /proc/mounts' > dagu-recovery-mounts.txt
adb shell 'cat /vendor/etc/fstab.qcom' > dagu-vendor-fstab.txt
adb shell 'cat /etc/additional.fstab' > dagu-additional-fstab.txt
adb shell 'ls -l /dev/block/bootdevice/by-name' > dagu-partitions.txt
adb shell dmesg > dagu-recovery-dmesg.txt
```

`additional.fstab` 是否存在以及日志中的 `Fstab:`、`Keymaster_Ver:`、QSEE、fscrypt 信息，可用于判断实际 vendor 参数是否被加载，再决定是否需要调整服务或替换配套内核。当前移植 ROM 的实际 vendor 版本和实机兼容性仍待确认。
