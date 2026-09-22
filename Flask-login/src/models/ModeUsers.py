from .entities.users import User

class ModelUser():

    @classmethod
    def login(cls, db, user):
        try:
            cursor = db.connection.cursor()
            sql = """
                                SELECT u.id, u.username, u.email, u.password, u.telefono, u.dni, u.foto_perfil,
                                             CASE
                                                 WHEN u.rol = 'organizador' AND NOT EXISTS (
                                                     SELECT 1 FROM organizer_role_requests r
                                                     WHERE r.user_id = u.id AND r.status = 'aprobada'
                                                 ) THEN 'estudiante'
                                                 ELSE u.rol
                                             END AS rol
                                FROM `user` u
                                WHERE u.email = %s OR u.username = %s
                        """
            cursor.execute(sql, (user.email, user.email))
            row = cursor.fetchone()
            
            if row != None:
                hashed_password = row[3]
                rol = (row[7] or 'estudiante').strip().lower() if len(row) > 7 else 'estudiante'
                user_match = User(
                    row[0],
                    row[1],
                    row[2],
                    User.check_password(hashed_password, user.password),
                    row[4],
                    row[5],
                    rol,
                    row[6]
                )
                return user_match
            else:
                return None
        except Exception as ex:
            raise Exception(ex)

    @classmethod
    def get_by_id(cls, db, id):
        try:
            cursor = db.connection.cursor()
            sql = """
                                SELECT u.id, u.username, u.email, u.telefono, u.dni, u.foto_perfil,
                                             CASE
                                                 WHEN u.rol = 'organizador' AND NOT EXISTS (
                                                     SELECT 1 FROM organizer_role_requests r
                                                     WHERE r.user_id = u.id AND r.status = 'aprobada'
                                                 ) THEN 'estudiante'
                                                 ELSE u.rol
                                             END AS rol
                                FROM `user` u
                                WHERE u.id = %s
                        """
            cursor.execute(sql, (id,))
            row = cursor.fetchone()
            
            if row != None:
                rol = (row[6] or 'estudiante').strip().lower() if len(row) > 6 else 'estudiante'
                return User(row[0], row[1], row[2], None, row[3], row[4], rol, row[5])
            else:
                return None
        except Exception as ex:
            raise Exception(ex)
    
    @classmethod
    def get_all_users(cls, db, dni=None):
        """Obtiene todos los usuarios, opcionalmente filtrados por DNI."""
        try:
            cursor = db.connection.cursor()
            sql = "SELECT id, username, email, telefono, dni, foto_perfil, rol FROM `user`"
            params = ()
            if dni:
                sql += " WHERE dni = %s"
                params = (dni,)
            sql += " ORDER BY id DESC"
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            
            users = []
            if rows:
                for row in rows:
                    rol = (row[6] or 'estudiante').strip().lower() if len(row) > 6 else 'estudiante'
                    user = User(row[0], row[1], row[2], None, row[3], row[4], rol, row[5])
                    users.append(user)
            
            return users
        except Exception as ex:
            print(f"[ERROR] get_all_users: {ex}")
            return []
    
    @classmethod
    def update_rol(cls, db, user_id, new_rol):
        """Actualiza el rol de un usuario"""
        try:
            cursor = db.connection.cursor()
            sql = "UPDATE `user` SET rol = %s WHERE id = %s"
            cursor.execute(sql, (new_rol, user_id))
            if new_rol == 'organizador':
                cursor.execute(
                    """
                    INSERT INTO organizer_role_requests (user_id, status, requested_at, reviewed_at)
                    SELECT %s, 'aprobada', NOW(), NOW()
                    WHERE NOT EXISTS (
                        SELECT 1 FROM organizer_role_requests
                        WHERE user_id = %s AND status = 'aprobada'
                    )
                    """,
                    (user_id, user_id)
                )
            db.connection.commit()
            return True
        except Exception as ex:
            raise Exception(ex)