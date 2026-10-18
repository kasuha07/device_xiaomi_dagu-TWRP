#
# Copyright (C) 2023 The Android Open Source Project
# Copyright (C) 2023 SebaUbuntu's TWRP device tree generator
#
# SPDX-License-Identifier: Apache-2.0
#

LOCAL_PATH := device/xiaomi/elish

# Dynamic Partitions
PRODUCT_USE_DYNAMIC_PARTITIONS := true

# Fastbootd
TW_INCLUDE_FASTBOOTD := true

# API
ifeq ($(PRODUCT_RELEASE_NAME),dagu)
# Verified against dagu V14.0.11.0.TLZCNXM recovery properties.
PRODUCT_TARGET_VNDK_VERSION := 30
PRODUCT_SHIPPING_API_LEVEL := 31
PRODUCT_PROPERTY_OVERRIDES += ro.twrp.keymaster=4.0
else
PRODUCT_TARGET_VNDK_VERSION := 31
PRODUCT_SHIPPING_API_LEVEL := 30
PRODUCT_PROPERTY_OVERRIDES += ro.twrp.keymaster=both
endif

# A/B
ENABLE_VIRTUAL_AB := true

# Boot Control HAL
PRODUCT_PACKAGES += \
    android.hardware.boot@1.1-impl-qti.recovery \
    bootctrl.kona.recovery

# Soong namespaces
PRODUCT_SOONG_NAMESPACES += \
    $(LOCAL_PATH)

# otacert
PRODUCT_EXTRA_RECOVERY_KEYS += \
    $(LOCAL_PATH)/security/miui_releasekey

# PRODUCT_RELEASE_NAME ro.twrp.device.name
PRODUCT_PROPERTY_OVERRIDES += ro.twrp.device.name=$(PRODUCT_RELEASE_NAME)

ifneq ($(TW_SKKK_VER_CODE),)
PRODUCT_PROPERTY_OVERRIDES += ro.twrp.version.skkk.code=$(TW_SKKK_VER_CODE)
endif

TWRP_REQUIRED_MODULES += miui_prebuilt \
    magisk_prebuilt
