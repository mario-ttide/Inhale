/* (inhale) A switch of this game's that has an Insert-menu row as well (gpu/vk/menu/kirby_env_rows.cpp): the environment
   variable when it is set, read as env_on_or reads it, else the row's line in inhale_options.ini (hos_ini_option,
   nn_applet.c), else def. The rows apply after a restart: the host reads the line where it read the variable alone. */
#pragma once

#ifndef INHALE_ENV_H
#include "../gpu/vk/compat/inhale_env.h"
#endif

int hos_ini_option(const char *key, int otherwise);   /* nn_applet.c */

static inline int kirby_option(const char *env, const char *key, int def) {
    const char *v = getenv(env);
    return v ? !env_value_off(v) : hos_ini_option(key, def) != 0;
}
