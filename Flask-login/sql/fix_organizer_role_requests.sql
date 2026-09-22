-- Crear tabla organizer_role_requests si no existe
CREATE TABLE IF NOT EXISTS `organizer_role_requests` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id` INT UNSIGNED NOT NULL,
  `status` ENUM('pendiente', 'aprobada', 'rechazada') NOT NULL DEFAULT 'pendiente',
  `requested_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `reviewed_at` DATETIME NULL,
  `reviewed_by` INT UNSIGNED NULL,
  PRIMARY KEY (`id`),
  KEY `idx_organizer_requests_user` (`user_id`),
  KEY `idx_organizer_requests_status` (`status`),
  FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
