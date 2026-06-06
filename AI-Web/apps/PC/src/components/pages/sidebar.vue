<script setup lang="ts">
import { MessageCircleDashed, Radiation, SettingsIcon } from 'lucide-vue-next';

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarRail,
  SidebarTrigger,
} from '../ui/sidebar';
</script>

<template>
  <SidebarProvider>
    <Sidebar>
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg">
              <div class="flex aspect-square size-8 items-center justify-center rounded-lg text-sidebar-primary-foreground" />
              <div class="flex flex-1 items-center justify-between text-left text-sm leading-tight">
                <span class="truncate font-semibold">Aura</span>
              </div>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton as-child>
                  <router-link to="/">
                    <MessageCircleDashed />
                    <span>Chat</span>
                  </router-link>
                </SidebarMenuButton>
                <SidebarMenuButton as-child>
                  <router-link to="/memory">
                    <Radiation />
                    <span>Memory</span>
                  </router-link>
                </SidebarMenuButton>
                <SidebarMenuButton as-child>
                  <router-link to="/seting">
                    <SettingsIcon />
                    <span>Settings</span>
                  </router-link>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter />
      <SidebarRail />
    </Sidebar>
    <SidebarInset>
      <header class="bg-background sticky top-0 z-10 flex h-16 shrink-0 items-center gap-2 transition-[width,height] ease-linear">
        <div class="flex items-center gap-2 px-4">
          <SidebarTrigger class="-ml-1" />
        </div>
      </header>
      <main class="h-full">
        <router-view />
      </main>
    </SidebarInset>
  </SidebarProvider>
</template>
