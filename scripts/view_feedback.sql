-- Просмотр оценок ответов (👍/👎) в PostgreSQL.
-- Запуск:
--   docker exec -it union_ai_apple_postgres psql -U gardener -d gardener -f - < scripts/view_feedback.sql
-- или интерактивно: \i scripts/view_feedback.sql (из psql в контейнере)

\echo '=== Сводка ==='
SELECT rating,
       CASE rating WHEN 1 THEN 'like' WHEN -1 THEN 'dislike' END AS kind,
       COUNT(*) AS cnt
FROM message_feedback
GROUP BY rating
ORDER BY rating;

\echo '=== Последние дизлайки (вопрос + ответ) ==='
SELECT mf.created_at AS feedback_at,
       cs.crop_id,
       u.telegram_id,
       mf.message_id,
       m_assist.session_id,
       (
           SELECT m2.content
           FROM messages m2
           WHERE m2.session_id = m_assist.session_id
             AND m2.role = 'user'
             AND m2.id < m_assist.id
           ORDER BY m2.id DESC
           LIMIT 1
       ) AS question,
       LEFT(m_assist.content, 300) AS answer_preview
FROM message_feedback mf
JOIN messages m_assist ON m_assist.id = mf.message_id AND m_assist.role = 'assistant'
JOIN chat_sessions cs ON cs.id = m_assist.session_id
JOIN users u ON u.id = mf.user_id
WHERE mf.rating = -1
ORDER BY mf.created_at DESC
LIMIT 30;

\echo '=== События message_feedback (analytics) ==='
SELECT created_at, payload
FROM analytics_events
WHERE event_type = 'message_feedback'
ORDER BY created_at DESC
LIMIT 20;
