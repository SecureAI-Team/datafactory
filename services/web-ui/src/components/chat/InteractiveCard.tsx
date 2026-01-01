import { useState } from 'react'
import { Check, ChevronRight, X, Loader2 } from 'lucide-react'
import clsx from 'clsx'

// Types
export interface InteractionOption {
  id: string
  label: string
  icon?: string
  description?: string
  next?: string
}

export interface InteractionStep {
  id: string
  question: string
  type: 'single' | 'multiple' | 'input'
  options?: InteractionOption[]
  inputType?: 'text' | 'number' | 'date'
  placeholder?: string
  validation?: {
    min?: number
    max?: number
    pattern?: string
    required?: boolean
  }
  required?: boolean
}

export interface InteractionProgress {
  answered: number
  total: number
}

interface InteractiveCardProps {
  flowName: string
  question: InteractionStep
  progress?: InteractionProgress
  onAnswer: (stepId: string, answer: string | string[]) => void
  onCancel: () => void
  isLoading?: boolean
}

// Icon mapping for common icons
const iconMap: Record<string, string> = {
  search: '🔍',
  grid: '📊',
  document: '📄',
  calculator: '🧮',
  users: '👥',
  chart: '📈',
  star: '⭐',
  check: '✅',
  box: '📦',
  tag: '🏷️',
  clock: '⏰',
  location: '📍',
  money: '💰',
  percent: '%',
}

export function InteractiveCard({
  flowName,
  question,
  progress,
  onAnswer,
  onCancel,
  isLoading = false,
}: InteractiveCardProps) {
  const [selectedOptions, setSelectedOptions] = useState<string[]>([])
  const [inputValue, setInputValue] = useState('')
  const [validationError, setValidationError] = useState<string | null>(null)

  const handleOptionClick = (optionId: string) => {
    if (question.type === 'single') {
      // Single select - immediately submit
      onAnswer(question.id, optionId)
    } else if (question.type === 'multiple') {
      // Multiple select - toggle selection
      setSelectedOptions((prev) =>
        prev.includes(optionId)
          ? prev.filter((id) => id !== optionId)
          : [...prev, optionId]
      )
    }
  }

  const handleSubmitMultiple = () => {
    if (selectedOptions.length === 0 && question.required !== false) {
      setValidationError('请至少选择一项')
      return
    }
    onAnswer(question.id, selectedOptions)
  }

  const handleSubmitInput = () => {
    // Validate input
    if (!inputValue.trim() && question.required !== false) {
      setValidationError('此字段为必填')
      return
    }

    if (question.validation) {
      const val = question.inputType === 'number' ? parseFloat(inputValue) : inputValue

      if (question.inputType === 'number' && isNaN(val as number)) {
        setValidationError('请输入有效数字')
        return
      }

      if (question.validation.min !== undefined && (val as number) < question.validation.min) {
        setValidationError(`最小值为 ${question.validation.min}`)
        return
      }

      if (question.validation.max !== undefined && (val as number) > question.validation.max) {
        setValidationError(`最大值为 ${question.validation.max}`)
        return
      }
    }

    setValidationError(null)
    onAnswer(question.id, inputValue)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmitInput()
    }
  }

  const getIcon = (iconName?: string) => {
    if (!iconName) return null
    return iconMap[iconName] || iconName
  }

  return (
    <div className="bg-gradient-to-br from-dark-800/90 to-dark-900/90 border border-dark-700/50 rounded-xl p-5 shadow-lg backdrop-blur-sm min-w-[360px] max-w-lg animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="text-xs text-dark-400 bg-dark-700/50 px-2 py-1 rounded-full">
            {flowName}
          </span>
          {progress && (
            <span className="text-xs text-dark-500">
              {progress.answered + 1} / {progress.total}
            </span>
          )}
        </div>
        <button
          onClick={onCancel}
          className="text-dark-500 hover:text-dark-300 transition-colors p-1 rounded-lg hover:bg-dark-700/50"
          title="取消"
        >
          <X size={16} />
        </button>
      </div>

      {/* Progress Bar */}
      {progress && (
        <div className="h-1 bg-dark-700 rounded-full mb-4 overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-primary-500 to-primary-400 transition-all duration-300"
            style={{ width: `${((progress.answered + 1) / progress.total) * 100}%` }}
          />
        </div>
      )}

      {/* Question */}
      <h3 className="text-base font-medium text-dark-100 mb-4">{question.question}</h3>

      {/* Options for single/multiple select */}
      {(question.type === 'single' || question.type === 'multiple') && question.options && (
        <div className="space-y-2 mb-4">
          {question.options.map((option) => {
            const isSelected = selectedOptions.includes(option.id)
            return (
              <button
                key={option.id}
                onClick={() => handleOptionClick(option.id)}
                disabled={isLoading}
                className={clsx(
                  'w-full flex items-center gap-3 p-3 rounded-lg border transition-all duration-200 text-left',
                  isSelected
                    ? 'border-primary-500 bg-primary-500/10 text-primary-300'
                    : 'border-dark-600 bg-dark-700/30 text-dark-200 hover:border-dark-500 hover:bg-dark-700/50',
                  isLoading && 'opacity-50 cursor-not-allowed'
                )}
              >
                {/* Selection indicator */}
                <div
                  className={clsx(
                    'w-5 h-5 rounded-full border-2 flex items-center justify-center flex-shrink-0',
                    question.type === 'multiple' ? 'rounded' : 'rounded-full',
                    isSelected
                      ? 'border-primary-500 bg-primary-500'
                      : 'border-dark-500'
                  )}
                >
                  {isSelected && <Check size={12} className="text-white" />}
                </div>

                {/* Icon */}
                {option.icon && (
                  <span className="text-lg flex-shrink-0">{getIcon(option.icon)}</span>
                )}

                {/* Label and description */}
                <div className="flex-1 min-w-0">
                  <div className="font-medium">{option.label}</div>
                  {option.description && (
                    <div className="text-xs text-dark-400 mt-0.5">{option.description}</div>
                  )}
                </div>

                {/* Arrow for single select */}
                {question.type === 'single' && (
                  <ChevronRight size={16} className="text-dark-500 flex-shrink-0" />
                )}
              </button>
            )
          })}
        </div>
      )}

      {/* Input field */}
      {question.type === 'input' && (
        <div className="mb-4">
          <div className="relative">
            <input
              type={question.inputType || 'text'}
              value={inputValue}
              onChange={(e) => {
                setInputValue(e.target.value)
                setValidationError(null)
              }}
              onKeyDown={handleKeyDown}
              placeholder={question.placeholder || '请输入...'}
              className={clsx(
                'w-full bg-dark-700/50 border rounded-lg px-4 py-3 text-dark-100 placeholder-dark-500',
                'focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500',
                validationError ? 'border-red-500' : 'border-dark-600'
              )}
              disabled={isLoading}
            />
          </div>
          {validationError && (
            <p className="text-red-400 text-xs mt-1">{validationError}</p>
          )}
          {question.validation && (
            <p className="text-dark-500 text-xs mt-1">
              {question.inputType === 'number' &&
                question.validation.min !== undefined &&
                question.validation.max !== undefined &&
                `范围: ${question.validation.min} - ${question.validation.max}`}
            </p>
          )}
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center justify-between">
        <button
          onClick={onCancel}
          className="text-dark-400 hover:text-dark-200 text-sm transition-colors"
          disabled={isLoading}
        >
          跳过
        </button>

        {(question.type === 'multiple' || question.type === 'input') && (
          <button
            onClick={question.type === 'input' ? handleSubmitInput : handleSubmitMultiple}
            disabled={isLoading}
            className={clsx(
              'flex items-center gap-2 px-4 py-2 rounded-lg font-medium text-sm transition-all',
              'bg-primary-500 hover:bg-primary-400 text-white',
              isLoading && 'opacity-50 cursor-not-allowed'
            )}
          >
            {isLoading ? (
              <>
                <Loader2 size={14} className="animate-spin" />
                处理中...
              </>
            ) : (
              <>
                下一步
                <ChevronRight size={14} />
              </>
            )}
          </button>
        )}
      </div>
    </div>
  )
}

export default InteractiveCard

