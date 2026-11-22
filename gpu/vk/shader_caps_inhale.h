// (inhale) What the translator may put in a program by what the device has: 8- and 16-bit integers (shaderInt8,
// shaderInt16). upstream's profile (vk_shader.cpp make_profile) says every device has them, and a module that declares the
// Int8 or Int16 capability without the feature is invalid (VUID-VkShaderModuleCreateInfo-pCode-08740): the driver need not
// accept it. Without them Eden converts through 32 bits. missing() goes into the program cache's stamp only when it is not
// 0, so every GPU that has both keeps its cache. HeyListen 6f82d229 (GPL-3.0); tests/test_shader_caps_inhale.py. (The
// 32-bit denorm modes of HeyListen 98f34e24 were here too: upstream's make_profile takes them from the device since v3.1.1)
#pragma once
#include <cstdint>
#include <vulkan/vulkan.h>

struct InhaleShaderCaps {
    bool int8 = true, int16 = true;
    uint32_t missing() const { return (int8 ? 0u : 1u) | (int16 ? 0u : 2u); }   // (a bit each that the device lacks)
};

inline InhaleShaderCaps inhale_shader_caps(const VkPhysicalDeviceFeatures& f, const VkPhysicalDeviceVulkan12Features& f12) {
    InhaleShaderCaps c;
    c.int8 = f12.shaderInt8 != VK_FALSE;
    c.int16 = f.shaderInt16 != VK_FALSE;
    return c;
}
