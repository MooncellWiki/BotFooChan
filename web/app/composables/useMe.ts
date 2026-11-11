import type { Me } from '~/client'

/** 当前登录的管理员，由 auth.global 路由中间件填上 */
export const useMe = () => useState<Me | null>('me', () => null)
