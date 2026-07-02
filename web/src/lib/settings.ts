// Model role overrides, persisted in localStorage.
const KEY = 'constellation_model_settings'

export type ModelSettings = Partial<Record<
  'architect' | 'persona_writer' | 'expert' | 'market_agent' | 'synthesizer' | 'workchart' | 'breakthrough' | 'pulse',
  string
>>

export function getModelSettings(): ModelSettings {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? '{}')
  } catch {
    return {}
  }
}

export function setModelSettings(settings: ModelSettings) {
  localStorage.setItem(KEY, JSON.stringify(settings))
}
