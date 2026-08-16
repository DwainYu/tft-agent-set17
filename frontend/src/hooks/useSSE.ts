import { useState, useCallback, useRef } from 'react';
import type { SSEStage, SSEEvent, CompCard, Direction } from '../types';
import { postAsk } from '../api/client';

export const STAGE_ORDER: SSEStage[] = [
  'understanding',
  'tool_selection',
  'tool_execution',
  'tool_done',
  'composing',
  'result',
];

export const STAGE_LABELS: Record<SSEStage, string> = {
  understanding: '理解问题',
  tool_selection: '选择工具',
  tool_execution: '执行查询',
  tool_done: '查询完成',
  composing: '整理结果',
  result: '最终结果',
};

interface AskResult {
  card: CompCard | Record<string, unknown> | null;
  results: Record<string, unknown>[];
  summary: string;
  reasoning: Partial<Record<SSEStage, string>>;
}

export function useSSE() {
  const [stage, setStage] = useState<SSEStage | null>(null);
  const [reasoning, setReasoning] = useState<Partial<Record<SSEStage, string>>>({});
  const [card, setCard] = useState<CompCard | Record<string, unknown> | null>(null);
  const [results, setResults] = useState<Record<string, unknown>[]>([]);
  const [summary, setSummary] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const ask = useCallback(async (question: string, direction?: Direction, conversationId?: string): Promise<AskResult> => {
    // Reset state
    setLoading(true);
    setError(null);
    setCard(null);
    setResults([]);
    setSummary('');
    setReasoning({});
    setStage('understanding');

    abortRef.current = new AbortController();

    // Local accumulator for reasoning text during this SSE session
    const reasoningAcc: Partial<Record<SSEStage, string>> = {};

    return new Promise<AskResult>((resolve, reject) => {
      postAsk(
        { question, direction, conversation_id: conversationId },
        (event: SSEEvent) => {
          if (event.stage === 'result' && event.data) {
            const cardData = event.data.card;
            const resultsData = event.data.results || [];
            const summaryText = event.data.summary || '';
            reasoningAcc['result' as SSEStage] = summaryText;

            setCard(cardData);
            setResults(resultsData);
            setSummary(summaryText);
            setReasoning({ ...reasoningAcc });

            resolve({
              card: cardData,
              results: resultsData,
              summary: summaryText,
              reasoning: { ...reasoningAcc },
            });
          } else if (event.content) {
            reasoningAcc[event.stage] = event.content;
            setReasoning({ ...reasoningAcc });
          }
          setStage(event.stage);
        },
        abortRef.current!.signal,
      ).catch((err: unknown) => {
        if (err instanceof Error && err.name !== 'AbortError') {
          setError(err.message);
          reject(err);
        }
      }).finally(() => {
        setLoading(false);
      });
    });
  }, []);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    setLoading(false);
  }, []);

  return { stage, reasoning, card, results, summary, loading, error, ask, cancel, STAGE_ORDER, STAGE_LABELS };
}
