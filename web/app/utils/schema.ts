/** pydantic 生成的 JSON Schema 里用得到的那部分 */
export interface JsonSchema {
  type?: string | string[]
  title?: string
  description?: string
  default?: unknown
  properties?: Record<string, JsonSchema>
  additionalProperties?: JsonSchema | boolean
  items?: JsonSchema
  uniqueItems?: boolean
  enum?: unknown[]
  const?: unknown
  $ref?: string
  $defs?: Record<string, JsonSchema>
  anyOf?: JsonSchema[]
  allOf?: JsonSchema[]
  minimum?: number
  maximum?: number
  exclusiveMinimum?: number
  exclusiveMaximum?: number
  required?: string[]
  // 后端字段上的标记（src/providers/settings/fields.py）
  secret?: boolean
  restart?: boolean
  model_ref?: boolean
  multiline?: boolean
  prompt?: boolean
}

/** 后端给密钥打码时的前缀，后面跟指纹；原样提交表示不改 */
export const SECRET_MASK = '••••••'

export function isMasked(value: unknown): boolean {
  return typeof value === 'string' && value.startsWith(SECRET_MASK)
}

/** 展开 $ref / 单个 allOf，去掉 Optional 里的 null；返回 [展开后的 schema, 是否可为 null] */
export function resolveSchema(schema: JsonSchema, root: JsonSchema): [JsonSchema, boolean] {
  let current = schema
  let nullable = false
  for (let i = 0; i < 10; i++) {
    if (current.$ref) {
      const { $ref, ...rest } = current
      const target = root.$defs?.[$ref.replace('#/$defs/', '')] ?? {}
      current = { ...target, ...rest }
    }
    else if (current.allOf?.length === 1) {
      const { allOf, ...rest } = current
      current = { ...allOf[0], ...rest }
    }
    else if (current.anyOf) {
      const others = current.anyOf.filter(s => s.type !== 'null')
      if (others.length === current.anyOf.length || others.length !== 1) break
      nullable = true
      const { anyOf: _, ...rest } = current
      current = { ...others[0], ...rest }
    }
    else {
      break
    }
  }
  return [current, nullable]
}

export type FieldKind = 'boolean' | 'integer' | 'number' | 'string' | 'enum' | 'tags' | 'object' | 'json'

/** 决定一个字段用什么控件；认不出来的（字典、对象列表……）退回 JSON 编辑 */
export function fieldKind(schema: JsonSchema): FieldKind {
  if (schema.enum) return 'enum'
  switch (schema.type) {
    case 'boolean': return 'boolean'
    case 'integer': return 'integer'
    case 'number': return 'number'
    case 'string': return 'string'
    case 'array': return schema.items?.type === 'string' && !schema.items.enum ? 'tags' : 'json'
    case 'object': return schema.properties && !schema.additionalProperties ? 'object' : 'json'
    default: return 'json'
  }
}

export function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/** 接口 422 的 detail 转成 {字段路径: 错误}，路径去掉开头的 body */
export function fieldErrors(error: unknown): Record<string, string> {
  const out: Record<string, string> = {}
  if (isPlainObject(error) && Array.isArray(error.detail)) {
    for (const item of error.detail as { loc?: (string | number)[], msg?: string }[]) {
      const path = (item.loc ?? []).filter(part => part !== 'body').join('.')
      if (path) out[path] = item.msg ?? ''
    }
  }
  return out
}
