CREATE DATABASE IF NOT EXISTS flask_login
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE flask_login;

DROP TABLE IF EXISTS `seguidores`;
DROP TABLE IF EXISTS `chats_eliminados`;
DROP TABLE IF EXISTS `respuestas_organizador`;
DROP TABLE IF EXISTS `mensajes_organizador`;
DROP TABLE IF EXISTS `recordatorios_eventos`;
DROP TABLE IF EXISTS `registrados`;
DROP TABLE IF EXISTS `organizer_role_requests`;
DROP TABLE IF EXISTS `event`;
DROP TABLE IF EXISTS `user`;

CREATE TABLE `user` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `username` VARCHAR(100) NOT NULL,
  `password` VARCHAR(255) NOT NULL,
  `telefono` VARCHAR(30) DEFAULT NULL,
  `email` VARCHAR(150) NOT NULL,
  `dni` VARCHAR(30) DEFAULT NULL,
  `rol` ENUM('estudiante', 'organizador', 'admin') NOT NULL DEFAULT 'estudiante',
  `foto_perfil` VARCHAR(255) DEFAULT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_user_email` (`email`),
  UNIQUE KEY `uq_user_username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `organizer_role_requests` (
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

CREATE TABLE `event` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `titulo` VARCHAR(200) NOT NULL,
  `fecha` DATE NOT NULL,
  `hora` TIME DEFAULT NULL,
  `descripcion` TEXT,
  `lugar` VARCHAR(200),
  `capacidad_maxima` INT NOT NULL,
  `finalizado` TINYINT(1) NOT NULL DEFAULT 0,
  `categoria` VARCHAR(100) DEFAULT 'General',
  `latitud` DECIMAL(10, 7) DEFAULT NULL,
  `longitud` DECIMAL(10, 7) DEFAULT NULL,
  `imagen` VARCHAR(255) DEFAULT NULL,
  `created_by` INT UNSIGNED NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `registrados` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `evento_id` INT UNSIGNED NOT NULL,
  `dni_usuario` VARCHAR(30) NOT NULL,
  `nombre_usuario` VARCHAR(150) NOT NULL,
  `qr_code` VARCHAR(255) NULL,
  `asistido` TINYINT(1) NOT NULL DEFAULT 0,
  `confirmado_at` DATETIME NULL,
  `metodo_confirmacion` VARCHAR(10) NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_registrados_evento_dni` (`evento_id`, `dni_usuario`),
  FOREIGN KEY (`evento_id`) REFERENCES `event` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `recordatorios_eventos` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `usuario_id` INT UNSIGNED NOT NULL,
  `evento_id` INT UNSIGNED NOT NULL,
  `tipo` VARCHAR(50) NOT NULL,
  `mensaje` TEXT NOT NULL,
  `fecha_programada` DATETIME NOT NULL,
  `enviado` TINYINT(1) NOT NULL DEFAULT 0,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_recordatorio_usuario` (`usuario_id`),
  KEY `idx_recordatorio_evento` (`evento_id`),
  KEY `idx_recordatorio_fecha` (`fecha_programada`),
  KEY `idx_recordatorio_enviado` (`enviado`),
  FOREIGN KEY (`usuario_id`) REFERENCES `user` (`id`) ON DELETE CASCADE,
  FOREIGN KEY (`evento_id`) REFERENCES `event` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `mensajes_organizador` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `organizador_id` INT UNSIGNED NOT NULL,
  `remitente_id` INT UNSIGNED NULL,
  `evento_id` INT UNSIGNED NOT NULL,
  `asunto` VARCHAR(255) NOT NULL,
  `mensaje` TEXT NOT NULL,
  `leido` TINYINT(1) DEFAULT 0,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_organizador` (`organizador_id`),
  KEY `idx_evento` (`evento_id`),
  KEY `idx_remitente` (`remitente_id`),
  KEY `idx_leido` (`leido`),
  FOREIGN KEY (`organizador_id`) REFERENCES `user` (`id`) ON DELETE CASCADE,
  FOREIGN KEY (`remitente_id`) REFERENCES `user` (`id`) ON DELETE SET NULL,
  FOREIGN KEY (`evento_id`) REFERENCES `event` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `respuestas_organizador` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `mensaje_id` INT UNSIGNED NOT NULL,
  `organizador_id` INT UNSIGNED NOT NULL,
  `destinatario_id` INT UNSIGNED DEFAULT NULL,
  `autor_id` INT UNSIGNED DEFAULT NULL,
  `respuesta` TEXT NOT NULL,
  `leido_destinatario` TINYINT(1) NOT NULL DEFAULT 0,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_mensaje` (`mensaje_id`),
  KEY `idx_organizador` (`organizador_id`),
  KEY `idx_destinatario` (`destinatario_id`),
  KEY `idx_autor` (`autor_id`),
  FOREIGN KEY (`mensaje_id`) REFERENCES `mensajes_organizador` (`id`) ON DELETE CASCADE,
  FOREIGN KEY (`organizador_id`) REFERENCES `user` (`id`) ON DELETE CASCADE,
  FOREIGN KEY (`destinatario_id`) REFERENCES `user` (`id`) ON DELETE SET NULL,
  FOREIGN KEY (`autor_id`) REFERENCES `user` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `seguidores` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `seguidor_id` INT UNSIGNED NOT NULL,
  `seguido_id` INT UNSIGNED NOT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_seguidor` (`seguidor_id`, `seguido_id`),
  KEY `idx_seguidor` (`seguidor_id`),
  KEY `idx_seguido` (`seguido_id`),
  FOREIGN KEY (`seguidor_id`) REFERENCES `user` (`id`) ON DELETE CASCADE,
  FOREIGN KEY (`seguido_id`) REFERENCES `user` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `chats_eliminados` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `usuario_id` INT UNSIGNED NOT NULL,
  `contacto_id` INT UNSIGNED NOT NULL,
  `eliminado_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_chat_usuario` (`usuario_id`, `contacto_id`),
  KEY `idx_chat_contacto` (`contacto_id`),
  FOREIGN KEY (`usuario_id`) REFERENCES `user` (`id`) ON DELETE CASCADE,
  FOREIGN KEY (`contacto_id`) REFERENCES `user` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


