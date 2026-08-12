SELECT u.id,
       u.email,
       s.expires_at
FROM users u
JOIN subscriptions s
    ON s.user_id = u.id
WHERE s.status = 'active'
  AND s.expires_at > NOW()
  AND NOT EXISTS (
      SELECT 1
      FROM meetings_attendance ma
      WHERE ma.user_id = u.id
        AND ma.date >= NOW() - INTERVAL '30 days'
  );