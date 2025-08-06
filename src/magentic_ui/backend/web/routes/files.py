# api/files.py
import os
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from loguru import logger

from ..deps import get_db
from ...datamodel import Run

router = APIRouter()


@router.get("/list/{run_id}")
async def list_files(run_id: int, db=Depends(get_db)) -> Dict[str, Any]:
    """
    获取指定 run 目录下的文件列表
    
    Args:
        run_id: Run ID
        db: 数据库依赖
        
    Returns:
        文件列表信息
    """
    try:
        # 获取 run 信息
        run_response = db.get(Run, filters={"id": run_id}, return_json=False)
        if not run_response.status or not run_response.data:
            raise HTTPException(status_code=404, detail="Run not found")
        
        run_data = run_response.data[0] if isinstance(run_response.data, list) else run_response.data
        
        # 构建文件目录路径
        workspace_path = os.environ.get("INTERNAL_WORKSPACE_ROOT", "./workspace")
        run_suffix = os.path.join(
            "files",
            "user",
            str(run_data.user_id or "unknown_user"),
            str(run_data.session_id or "unknown_session"),
            str(run_data.id or "unknown_run"),
        )
        run_dir = os.path.join(workspace_path, run_suffix)
        
        # 检查目录是否存在
        if not os.path.exists(run_dir):
            return {"status": True, "data": {"files": [], "directory": run_dir}}
        
        # 获取文件列表
        exclude_files = ["supervisord.pid"]
        files = []
        for item in os.listdir(run_dir):
            if item in exclude_files:
                continue
            item_path = os.path.join(run_dir, item)
            if os.path.isfile(item_path):
                stat = os.stat(item_path)
                files.append({
                    "name": item,
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                    "type": "file"
                })
            elif os.path.isdir(item_path):
                stat = os.stat(item_path)
                files.append({
                    "name": item,
                    "size": 0,
                    "modified": stat.st_mtime,
                    "type": "directory"
                })
        
        # 按修改时间排序
        files.sort(key=lambda x: x["modified"], reverse=True)
        
        return {
            "status": True, 
            "data": {
                "files": files,
                "directory": run_dir,
                "run_id": run_id
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing files for run {run_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/upload/{run_id}")
async def upload_file(
    run_id: int, 
    file: UploadFile = File(...),
    db=Depends(get_db)
) -> Dict[str, Any]:
    """
    上传文件到指定 run 目录
    
    Args:
        run_id: Run ID
        file: 上传的文件
        db: 数据库依赖
        
    Returns:
        上传结果
    """
    try:
        # 获取 run 信息
        run_response = db.get(Run, filters={"id": run_id}, return_json=False)
        if not run_response.status or not run_response.data:
            raise HTTPException(status_code=404, detail="Run not found")
        
        run_data = run_response.data[0] if isinstance(run_response.data, list) else run_response.data
        
        # 构建文件目录路径
        workspace_path = os.environ.get("INTERNAL_WORKSPACE_ROOT", "/app/workspace")
        run_suffix = os.path.join(
            "files",
            "user",
            str(run_data.user_id or "unknown_user"),
            str(run_data.session_id or "unknown_session"),
            str(run_data.id or "unknown_run"),
        )
        run_dir = os.path.join(workspace_path, run_suffix)
        
        # 创建目录
        os.makedirs(run_dir, exist_ok=True)
        
        # 保存文件
        if not file.filename:
            raise HTTPException(status_code=400, detail="Filename is required")
            
        file_path = os.path.join(run_dir, file.filename)
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        logger.info(f"File uploaded: {file_path}")
        
        return {
            "status": True,
            "data": {
                "filename": file.filename,
                "size": len(content),
                "path": file_path
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file for run {run_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/download/{run_id}")
async def download_file(
    run_id: int, 
    filename: str,
    db=Depends(get_db)
):
    """
    下载指定 run 目录下的文件
    
    Args:
        run_id: Run ID
        filename: 文件名
        db: 数据库依赖
        
    Returns:
        文件下载响应
    """
    try:
        # 获取 run 信息
        run_response = db.get(Run, filters={"id": run_id}, return_json=False)
        if not run_response.status or not run_response.data:
            raise HTTPException(status_code=404, detail="Run not found")
        
        run_data = run_response.data[0] if isinstance(run_response.data, list) else run_response.data
        
        # 构建文件路径
        workspace_path = os.environ.get("INTERNAL_WORKSPACE_ROOT", "./workspace")
        run_suffix = os.path.join(
            "files",
            "user",
            str(run_data.user_id or "unknown_user"),
            str(run_data.session_id or "unknown_session"),
            str(run_data.id or "unknown_run"),
        )
        run_dir = os.path.join(workspace_path, run_suffix)
        file_path = os.path.join(run_dir, filename)
        
        # 检查文件是否存在
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")
        
        if not os.path.isfile(file_path):
            raise HTTPException(status_code=400, detail="Path is not a file")
        
        # 返回文件下载响应
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type='application/octet-stream'
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading file {filename} for run {run_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/delete/{run_id}")
async def delete_file(
    run_id: int, 
    filename: str,
    db=Depends(get_db)
) -> Dict[str, Any]:
    """
    删除指定 run 目录下的文件
    
    Args:
        run_id: Run ID
        filename: 文件名
        db: 数据库依赖
        
    Returns:
        删除结果
    """
    try:
        # 获取 run 信息
        run_response = db.get(Run, filters={"id": run_id}, return_json=False)
        if not run_response.status or not run_response.data:
            raise HTTPException(status_code=404, detail="Run not found")
        
        run_data = run_response.data[0] if isinstance(run_response.data, list) else run_response.data
        
        # 构建文件路径
        workspace_path = os.environ.get("INTERNAL_WORKSPACE_ROOT", "./workspace")
        run_suffix = os.path.join(
            "files",
            "user",
            str(run_data.user_id or "unknown_user"),
            str(run_data.session_id or "unknown_session"),
            str(run_data.id or "unknown_run"),
        )
        run_dir = os.path.join(workspace_path, run_suffix)
        file_path = os.path.join(run_dir, filename)
        
        # 检查文件是否存在
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")
        
        if not os.path.isfile(file_path):
            raise HTTPException(status_code=400, detail="Path is not a file")
        
        # 删除文件
        os.remove(file_path)
        logger.info(f"File deleted: {file_path}")
        
        return {
            "status": True,
            "data": {
                "filename": filename,
                "message": "File deleted successfully"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting file {filename} for run {run_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
