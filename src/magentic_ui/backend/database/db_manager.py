import threading
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional, Union, Dict

from loguru import logger
from sqlalchemy import exc, inspect, text
from sqlmodel import Session, SQLModel, and_, create_engine, select

from ..datamodel import DatabaseModel, Response, Team
from ..teammanager import TeamManager
from .schema_manager import SchemaManager


class DatabaseManager:
    _init_lock = threading.Lock()

    def _add_column_if_not_exists(self, connection: Any, table_name: str, column_name: str, column_def: str) -> None:
        """Helper to add a column to a table if it doesn't already exist."""
        # For SQLite, checking PRAGMA table_info is more robust than trying/excepting ALTER TABLE
        result = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
        if not any(row[1] == column_name for row in result): # row[1] is the column name in PRAGMA table_info
            try:
                connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}"))
                logger.info(f"Added column '{column_name}' to table '{table_name}'.")
            except Exception as e: # Broad exception for safety, specific exceptions (e.g., OperationalError) can be caught
                logger.warning(f"Could not add column '{column_name}' to table '{table_name}': {e}. It might already exist or table doesn't exist yet.")
        else:
            logger.debug(f"Column '{column_name}' already exists in table '{table_name}'.")

    def __init__(self, engine_uri: str, base_dir: Optional[Path] = None):
        """
        Initialize DatabaseManager with database connection settings.
        Does not perform any database operations.

        Args:
            engine_uri (str): Database connection URI (e.g. sqlite:///db.sqlite3)
            base_dir (Path, optional): Base directory for migration files. If None, uses current directory. Default: None.
        """
        connection_args = {"check_same_thread": True} if "sqlite" in engine_uri else {}

        self.engine = create_engine(engine_uri, connect_args=connection_args)
        self.schema_manager = SchemaManager(
            engine=self.engine,
            base_dir=base_dir,
        )

    def _should_auto_upgrade(self) -> bool:
        """
        Check if auto upgrade should run based on schema differences
        """
        needs_upgrade, _ = self.schema_manager.check_schema_status()
        return needs_upgrade

    def initialize_database(
        self, auto_upgrade: bool = False, force_init_alembic: bool = True
    ) -> Response:
        """
        Initialize database and migrations in the correct order.

        Args:
            auto_upgrade (bool, optional): If True, automatically generate and apply migrations for schema changes. Default: False.
            force_init_alembic (bool, optional): If True, reinitialize alembic configuration even if it exists. Default: True
        """
        if not self._init_lock.acquire(blocking=False):
            return Response(
                message="Database initialization already in progress", status=False
            )

        try:
            # Enable foreign key constraints for SQLite
            if "sqlite" in str(self.engine.url):
                with self.engine.connect() as conn:
                    conn.execute(text("PRAGMA foreign_keys=ON"))
            inspector = inspect(self.engine)
            tables_exist = inspector.get_table_names()
            if not tables_exist:
                logger.info("Creating database tables (base SQLModel)...")
                SQLModel.metadata.create_all(self.engine)
                # Further ensure our specific tables are created
                with self.engine.connect() as connection:
                    with connection.begin(): # Start a transaction
                        logger.info("Ensuring Magentic UI review tables and columns exist (initial creation path)...")
                        self._ensure_review_tables(connection) # This will also try to add columns to 'runs'
                    logger.info("Magentic UI review tables and columns ensured (initial creation path).")

                if self.schema_manager.initialize_migrations(force=force_init_alembic):
                    return Response(
                        message="Database initialized successfully", status=True
                    )
                return Response(message="Failed to initialize migrations", status=False)

            # Handle existing database - also ensure our tables are there
            # This is important if the DB was created by SQLModel.metadata.create_all
            # but before these tables were added to this direct execution block.
            with self.engine.connect() as connection:
                with connection.begin(): # Start a transaction
                        logger.info("Ensuring Magentic UI review tables and columns exist (update path)...")
                        self._ensure_review_tables(connection) # This will also try to add columns to 'runs'
                logger.info("Magentic UI review tables and columns ensured (update path).")

            if auto_upgrade or self._should_auto_upgrade():
                logger.info("Checking database schema...")
                if self.schema_manager.ensure_schema_up_to_date():
                    return Response(
                        message="Database schema is up to date", status=True
                    )
                return Response(message="Database upgrade failed", status=False)

            return Response(message="Database is ready", status=True)

        except Exception as e:
            error_msg = f"Database initialization failed: {str(e)}"
            logger.error(error_msg)
            return Response(message=error_msg, status=False)
        finally:
            self._init_lock.release()

    def _ensure_review_tables(self, connection: Any) -> None:
        """Helper to execute CREATE TABLE statements for review feature and add new columns to 'runs'."""
        
        # Add new columns to the 'runs' table if they don't exist
        # Assuming 'runs' table is created by SQLModel.metadata.create_all elsewhere or earlier.
        # These calls are designed to be safe even if 'runs' doesn't exist when this is first called
        # during initial SQLModel.metadata.create_all, as PRAGMA table_info would return nothing.
        self._add_column_if_not_exists(connection, "runs", "human_confirmed_completion", "BOOLEAN DEFAULT FALSE")
        self._add_column_if_not_exists(connection, "runs", "comprehensive_summary", "TEXT")

        # Continue with creating other review-specific tables
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS a2a_planning_suggestions (
                suggestion_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                source_agent_uri TEXT,
                suggestion_content TEXT NOT NULL,
                received_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (run_id) REFERENCES runs (id) ON DELETE CASCADE
            );
        """))
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS plan_versions (
                plan_version_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                version_number INTEGER NOT NULL,
                plan_type TEXT NOT NULL,
                plan_task_description TEXT,
                plan_summary TEXT,
                plan_content TEXT NOT NULL,
                is_current_plan BOOLEAN DEFAULT FALSE,
                creation_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (run_id, version_number),
                FOREIGN KEY (run_id) REFERENCES runs (id) ON DELETE CASCADE
            );
        """))
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS plan_step_executions (
                step_execution_id TEXT PRIMARY KEY,
                plan_version_id TEXT NOT NULL,
                step_index INTEGER NOT NULL,
                step_title TEXT,
                step_details TEXT,
                assigned_agent_name TEXT,
                instruction_given TEXT,
                start_timestamp DATETIME,
                end_timestamp DATETIME,
                status TEXT,
                agent_response_summary TEXT,
                progress_summary_at_step_end TEXT,
                creation_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (plan_version_id) REFERENCES plan_versions (plan_version_id) ON DELETE CASCADE
            );
        """))
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS agent_actions (
                action_id TEXT PRIMARY KEY,
                step_execution_id TEXT NOT NULL,
                action_sequence_number INTEGER NOT NULL,
                agent_name TEXT,
                action_type TEXT NOT NULL,
                action_name TEXT,
                parameters TEXT,
                outcome_summary TEXT,
                raw_log_references TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (step_execution_id) REFERENCES plan_step_executions (step_execution_id) ON DELETE CASCADE
            );
        """))
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS approval_events (
                approval_event_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                step_execution_id TEXT,
                action_id TEXT,
                action_presented TEXT NOT NULL,
                user_response TEXT,
                outcome BOOLEAN NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (run_id) REFERENCES runs (id) ON DELETE CASCADE,
                FOREIGN KEY (step_execution_id) REFERENCES plan_step_executions (step_execution_id) ON DELETE SET NULL,
                FOREIGN KEY (action_id) REFERENCES agent_actions (action_id) ON DELETE SET NULL
            );
        """))
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS a2a_intervention_messages (
                intervention_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                step_execution_id TEXT,
                source_agent_uri TEXT,
                intervention_content TEXT NOT NULL,
                received_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                replan_triggered BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (run_id) REFERENCES runs (id) ON DELETE CASCADE,
                FOREIGN KEY (step_execution_id) REFERENCES plan_step_executions (step_execution_id) ON DELETE SET NULL
            );
        """))

    def reset_db(self, recreate_tables: bool = True) -> Response:
        """
        Reset the database by dropping all tables and optionally recreating them.

        Args:
            recreate_tables (bool, optional): If True, recreates the tables after dropping them. Set to False if you want to call create_db_and_tables() separately. Default: True.
        """
        if not self._init_lock.acquire(blocking=False):
            logger.warning("Database reset already in progress")
            return Response(
                message="Database reset already in progress", status=False, data=None
            )

        try:
            # Dispose existing connections
            self.engine.dispose()
            with Session(self.engine) as session:
                try:
                    # Disable foreign key checks for SQLite
                    if "sqlite" in str(self.engine.url):
                        session.connection().execute(text("PRAGMA foreign_keys=OFF"))

                    # Drop all tables
                    SQLModel.metadata.drop_all(self.engine) # This will drop all tables including the new ones
                    logger.info("All tables dropped successfully")

                    # Re-enable foreign key checks for SQLite
                    if "sqlite" in str(self.engine.url):
                        session.connection().execute(text("PRAGMA foreign_keys=ON"))

                    session.commit()
                except Exception as e:
                    session.rollback()
                    # No need to release lock here, it's handled by the outer finally
                    raise e
                finally:
                    session.close() # Close session in its own finally

            if recreate_tables:
                logger.info("Recreating tables...")
                self.initialize_database(auto_upgrade=False, force_init_alembic=True)

            return Response(
                message="Database reset successfully"
                if recreate_tables
                else "Database tables dropped successfully",
                status=True,
                data=None,
            )

        except Exception as e:
            error_msg = f"Error while resetting database: {str(e)}"
            logger.error(error_msg)
            return Response(message=error_msg, status=False, data=None)
        # Ensure lock is released in all paths for reset_db
        finally:
            if self._init_lock.locked(): # Check if the current thread holds the lock
                self._init_lock.release()
                logger.info("Database reset lock released by current thread.")

    def upsert(self, model: DatabaseModel, return_json: bool = True) -> Response:
        """Create or update an entity

        Args:
            model (DatabaseModel): The model instance to create or update
            return_json (bool, optional): If True, returns the model as a dictionary. If False, returns the SQLModel instance. Default: True.

        Returns:
            Response: Contains status, message and data (either dict or SQLModel based on return_json)
        """
        status = True
        model_class = type(model)
        existing_model = None

        with Session(self.engine) as session:
            try:
                existing_model = session.exec(
                    select(model_class).where(model_class.id == model.id)
                ).first()
                if existing_model:
                    model.updated_at = datetime.now()
                    for key, value in model.model_dump().items():
                        setattr(existing_model, key, value)
                    model = existing_model  # Use the updated existing model
                    session.add(model)
                else:
                    session.add(model)
                session.commit()
                session.refresh(model)
            except Exception as e:
                session.rollback()
                logger.error(
                    "Error while updating/creating "
                    + str(model_class.__name__)
                    + ": "
                    + str(e)
                )
                status = False

        return Response(
            message=(
                f"{model_class.__name__} Updated Successfully"
                if existing_model
                else f"{model_class.__name__} Created Successfully"
            ),
            status=status,
            data=model.model_dump() if return_json else model,
        )

    def get(
        self,
        model_class: type[DatabaseModel],
        filters: dict[str, Any] | None = None,
        return_json: bool = False,
        order: str = "desc",
    ) -> Response:
        """List entities"""
        with Session(self.engine) as session:
            result = []
            status = True
            status_message = ""

            try:
                statement = select(model_class)
                if filters:
                    conditions = [
                        getattr(model_class, col) == value
                        for col, value in filters.items()
                    ]
                    statement = statement.where(and_(*conditions))

                if hasattr(model_class, "created_at") and order:
                    order_by_clause = getattr(
                        model_class.created_at, order
                    )()  # Dynamically apply asc/desc
                    statement = statement.order_by(order_by_clause)

                items = session.exec(statement).all()
                result = [
                    item.model_dump(mode="json") if return_json else item
                    for item in items
                ]
                status_message = f"{model_class.__name__} Retrieved Successfully"
            except Exception as e:
                session.rollback()
                status = False
                status_message = f"Error while fetching {model_class.__name__}"
                logger.error(
                    "Error while getting items: "
                    + str(model_class.__name__)
                    + " "
                    + str(e)
                )

            return Response(message=status_message, status=status, data=result)

    def delete(
        self, model_class: type[SQLModel], filters: dict[str, Any] | None = None
    ) -> Response:
        """Delete an entity"""
        status_message = ""
        status = True

        with Session(self.engine) as session:
            try:
                if "sqlite" in str(self.engine.url):
                    session.connection().execute(text("PRAGMA foreign_keys=ON"))
                statement = select(model_class)
                if filters:
                    conditions = [
                        getattr(model_class, col) == value
                        for col, value in filters.items()
                    ]
                    statement = statement.where(and_(*conditions))

                rows = session.exec(statement).all()

                if rows:
                    for row in rows:
                        session.delete(row)
                    session.commit()
                    status_message = f"{model_class.__name__} Deleted Successfully"
                else:
                    status_message = "Row not found"
                    logger.info(f"Row with filters {filters} not found")

            except exc.IntegrityError as e:
                session.rollback()
                status = False
                status_message = f"Integrity error: The {model_class.__name__} is linked to another entity and cannot be deleted. {e}"
                # Log the specific integrity error
                logger.error(status_message)
            except Exception as e:
                session.rollback()
                status = False
                status_message = f"Error while deleting: {e}"
                logger.error(status_message)

        return Response(message=status_message, status=status, data=None)

    async def import_team(
        self,
        team_config: Union[str, Path, Dict[str, Any]],
        user_id: str,
        check_exists: bool = False,
    ) -> Response:
        try:
            # Load config if path provided
            if isinstance(team_config, (str, Path)):
                config = await TeamManager.load_from_file(team_config)
            else:
                config = team_config

            # Check existence if requested
            if check_exists:
                existing = await self._check_team_exists(config, user_id)
                if existing:
                    return Response(
                        message="Identical team configuration already exists",
                        status=True,
                        data={"id": existing.id},
                    )

            # Store in database
            team_db = Team(user_id=user_id, component=config, created_at=datetime.now())

            result = self.upsert(team_db)
            return result

        except Exception as e:
            logger.error(f"Failed to import team: {str(e)}")
            return Response(message=str(e), status=False)

    async def import_teams_from_directory(
        self, directory: Union[str, Path], user_id: str, check_exists: bool = False
    ) -> Response:
        """
        Import all team configurations from a directory.

        Args:
            directory (str | Path): Path to directory containing team configs
            user_id (str): User ID to associate with imported teams
            check_exists (bool, optional): Whether to check for existing teams. Default: False.

        Returns:
            Response: Contains import results for all files
        """
        try:
            # Load all configs from directory
            configs = await TeamManager.load_from_directory(directory)

            results: List[Dict[str, Any]] = []
            for config in configs:
                try:
                    result = await self.import_team(
                        team_config=config, user_id=user_id, check_exists=check_exists
                    )

                    if not result.data:
                        raise ValueError("No data returned from import")

                    # Add result info
                    results.append(
                        {
                            "status": result.status,
                            "message": result.message,
                            "id": result.data.get("id") if result.status else None,
                        }
                    )

                except Exception as e:
                    logger.error(f"Failed to import team config: {str(e)}")
                    results.append({"status": False, "message": str(e), "id": None})

            return Response(
                message="Directory import complete", status=True, data=results
            )

        except Exception as e:
            logger.error(f"Failed to import directory: {str(e)}")
            return Response(message=str(e), status=False)

    async def _check_team_exists(
        self, config: Dict[str, Any], user_id: str
    ) -> Optional[Team]:
        """Check if identical team config already exists"""
        teams = self.get(Team, {"user_id": user_id}).data

        if not teams:
            return None

        for team in teams:
            if team.component == config:
                return team

        return None

    async def close(self) -> None:
        """Close database connections and cleanup resources"""
        logger.info("Closing database connections...")
        try:
            # Dispose of the SQLAlchemy engine
            self.engine.dispose()
            logger.info("Database connections closed successfully")
        except Exception as e:
            logger.error(f"Error closing database connections: {str(e)}")
            raise
