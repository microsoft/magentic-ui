import React, { useState, useEffect, useRef } from "react";
import {
  Upload,
  Download,
  Trash2,
  RefreshCw,
  FileText,
  Image as ImageIcon,
  Folder,
  File,
} from "lucide-react";
import { Button, message, Modal, Upload as AntUpload } from "antd";
import type { UploadFile, UploadProps } from "antd/es/upload/interface";
import { getServerUrl } from "../../../utils";
import { useTranslation } from "react-i18next";

interface FileInfo {
  name: string;
  size: number;
  modified: number;
  type: "file" | "directory";
}

interface FilesViewerProps {
  runId: number;
  className?: string;
}

const FilesViewer: React.FC<FilesViewerProps> = ({ runId, className = "" }) => {
  const { t } = useTranslation();
  const [files, setFiles] = useState<FileInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploadModalVisible, setUploadModalVisible] = useState(false);
  const [uploadFileList, setUploadFileList] = useState<UploadFile[]>([]);
  const [uploading, setUploading] = useState(false);
  
  // 添加原生文件上传的 ref
  const fileInputRef = useRef<HTMLInputElement>(null);

  // 获取文件列表
  const fetchFiles = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${getServerUrl()}/files/list/${runId}`);
      const result = await response.json();
      
      if (result.status) {
        setFiles(result.data.files || []);
      } else {
        message.error("Failed to load files");
      }
    } catch (error) {
      console.error("Error fetching files:", error);
      message.error("Failed to load files");
    } finally {
      setLoading(false);
    }
  };

  // 下载文件
  const handleDownload = async (filename: string) => {
    try {
      const response = await fetch(`${getServerUrl()}/files/download/${runId}?filename=${encodeURIComponent(filename)}`);
      
      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        message.success(`Downloaded ${filename}`);
      } else {
        message.error("Failed to download file");
      }
    } catch (error) {
      console.error("Error downloading file:", error);
      message.error("Failed to download file");
    }
  };

  // 删除文件
  const handleDelete = async (filename: string) => {
    Modal.confirm({
      title: "Delete File",
      content: `Are you sure you want to delete "${filename}"?`,
      okText: "Delete",
      okType: "danger",
      cancelText: "Cancel",
      onOk: async () => {
        try {
          const response = await fetch(`${getServerUrl()}/files/delete/${runId}?filename=${encodeURIComponent(filename)}`, {
            method: "DELETE",
          });
          
          const result = await response.json();
          
          if (result.status) {
            message.success(`Deleted ${filename}`);
            fetchFiles(); // 刷新文件列表
          } else {
            message.error("Failed to delete file");
          }
        } catch (error) {
          console.error("Error deleting file:", error);
          message.error("Failed to delete file");
        }
      },
    });
  };

  // 上传文件
  const handleUpload = async () => {
    console.log("Upload button clicked, fileList:", uploadFileList);
    
    if (uploadFileList.length === 0) {
      message.warning("Please select files to upload");
      return;
    }

    setUploading(true);
    try {
      for (const file of uploadFileList) {
        console.log("Processing file:", file);
        console.log("File type:", typeof file);
        // console.log("File instanceof File:", file instanceof File);
        // console.log("File properties:", Object.keys(file));
        // console.log("File.originFileObj:", file.originFileObj);
        
        // 尝试多种方式获取文件对象
        let fileObj = null;
        
        // 方法1: 直接使用文件对象
        if (file && typeof file === 'object' && 'name' in file) {
          fileObj = file;
        }
        // 方法2: 使用 originFileObj
        else if ((file as any).originFileObj && typeof (file as any).originFileObj === 'object' && 'name' in (file as any).originFileObj) {
          fileObj = (file as any).originFileObj;
        }
        // 方法3: 检查是否有其他属性包含文件数据
        else if ((file as any).file && typeof (file as any).file === 'object' && 'name' in (file as any).file) {
          fileObj = (file as any).file;
        }
        
        if (fileObj) {
          // 验证文件类型和大小
          if (!validateFile(fileObj)) {
            console.log(`Invalid file: ${file.name}`);
            continue; // 跳过无效文件
          }
          try {
            const formData = new FormData();
            formData.append("file", fileObj);
            
            console.log(`Uploading ${file.name} to ${getServerUrl()}/files/upload/${runId}`);
            
            const response = await fetch(`${getServerUrl()}/files/upload/${runId}`, {
              method: "POST",
              body: formData,
            });

            const result = await response.json();
            
            if (result.status) {
              message.success(`Uploaded ${file.name}`);
            } else {
              message.error(`Failed to upload ${file.name}: ${result.message || 'Unknown error'}`);
            }
          } catch (uploadError) {
            console.error("Upload error:", uploadError);
            const errorMessage = uploadError instanceof Error ? uploadError.message : 'Unknown error';
            message.error(`Failed to upload ${file.name}: ${errorMessage}`);
          }
        } else {
          console.error("Could not extract valid file object from:", file);
          message.error(`Could not process file: ${file.name}`);
        }
      }
      
      setUploadModalVisible(false);
      setUploadFileList([]);
      fetchFiles(); // 刷新文件列表
    } catch (error) {
      console.error("Error uploading files:", error);
      message.error("Failed to upload files");
    } finally {
      setUploading(false);
    }
  };

  // 获取文件图标
  const getFileIcon = (file: FileInfo) => {
    if (file.type === "directory") {
      return <Folder className="w-4 h-4 text-blue-500" />;
    }
    
    const extension = file.name.split('.').pop()?.toLowerCase();
    switch (extension) {
      case 'txt':
      case 'md':
      case 'csv':
      case 'json':
      case 'py':
      case 'js':
      case 'ts':
      case 'html':
      case 'css':
        return <FileText className="w-4 h-4 text-green-500" />;
      case 'jpg':
      case 'jpeg':
      case 'png':
      case 'gif':
      case 'svg':
        return <ImageIcon className="w-4 h-4 text-purple-500" />;
      case 'xls':
      case 'xlsx':
        return <FileText className="w-4 h-4 text-green-600" />; // Excel 文件使用深绿色
      default:
        return <File className="w-4 h-4 text-gray-500" />;
    }
  };

  // 格式化文件大小
  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  // 格式化时间
  const formatTime = (timestamp: number) => {
    return new Date(timestamp * 1000).toLocaleString();
  };

  // 允许的文件类型
  const ALLOWED_FILE_TYPES = [
    "text/plain",
    "text/csv",
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/svg+xml",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  ];

  // 最大文件大小 (50MB)
  const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB in bytes

  // 文件验证函数
  const validateFile = (file: any) => {
    // 检查文件类型
    if (!ALLOWED_FILE_TYPES.includes(file.type)) {
      message.error(`File type ${file.type} is not allowed. Allowed types: ${ALLOWED_FILE_TYPES.join(', ')}`);
      return false;
    }
    
    // 检查文件大小
    if (file.size > MAX_FILE_SIZE) {
      message.error(`File size ${(file.size / 1024 / 1024).toFixed(2)}MB exceeds the maximum allowed size of 50MB`);
      return false;
    }
    
    return true;
  };

  // 上传配置
  const uploadProps: UploadProps = {
    onRemove: (file) => {
      const index = uploadFileList.indexOf(file);
      const newFileList = uploadFileList.slice();
      newFileList.splice(index, 1);
      setUploadFileList(newFileList);
    },
    beforeUpload: (file) => {
      console.log("File selected:", file);
      
      // 验证文件
      if (!validateFile(file)) {
        return false;
      }
      
      setUploadFileList((prev) => [...prev, file]);
      return false; // 阻止自动上传
    },
    fileList: uploadFileList,
    multiple: true,
    accept: ALLOWED_FILE_TYPES.join(','), // 限制接受的文件类型
  };

  useEffect(() => {
    fetchFiles();
  }, [runId]);

  return (
    <div className={`flex flex-col h-full ${className}`}>
      {/* 工具栏 */}
      <div className="flex justify-between items-center mb-4 p-4 border-b">
        <h3 className="text-lg font-semibold">Files</h3>
        <div className="flex gap-2">
          <Button
            icon={<RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />}
            onClick={fetchFiles}
            loading={loading}
          >
            {t('filesViewer.refresh')}
          </Button>
          <Button
            type="primary"
            icon={<Upload className="w-4 h-4" />}
            onClick={() => setUploadModalVisible(true)}
          >
            {t('filesViewer.upload')}
          </Button>
        </div>
      </div>

      {/* 文件列表 */}
      <div className="flex-1 overflow-auto p-4">
        {files.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-gray-500">
            <Folder className="w-16 h-16 mb-4" />
            <p>{t('filesViewer.noFilesFound')}</p>
            <p className="text-sm">{t('filesViewer.uploadFilesToGetStarted')}</p>
          </div>
        ) : (
          <div className="space-y-2">
            {files.map((file) => (
              <div
                key={file.name}
                className="flex items-center justify-between p-3 border rounded-lg hover:bg-gray-50 transition-colors"
              >
                <div className="flex items-center gap-3 flex-1 min-w-0">
                  {getFileIcon(file)}
                  <div className="flex-1 min-w-0">
                    <p className="font-medium truncate">{file.name}</p>
                    <p className="text-sm text-gray-500">
                      {file.type === "file" ? formatFileSize(file.size) : "Directory"} • {formatTime(file.modified)}
                    </p>
                  </div>
                </div>
                
                {file.type === "file" && (
                  <div className="flex gap-2">
                    <Button
                      size="small"
                      icon={<Download className="w-3 h-3" />}
                      onClick={() => handleDownload(file.name)}
                    >
                      {t('filesViewer.download')}
                    </Button>
                    <Button
                      size="small"
                      danger
                      icon={<Trash2 className="w-3 h-3" />}
                      onClick={() => handleDelete(file.name)}
                    >
                      {t('filesViewer.delete')}
                    </Button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 上传模态框 */}
      <Modal
        title={t('filesViewer.uploadFiles')}
        open={uploadModalVisible}
        onCancel={() => {
          setUploadModalVisible(false);
          setUploadFileList([]);
        }}
        onOk={handleUpload}
        confirmLoading={uploading}
        okText={t('filesViewer.upload')}
        cancelText={t('filesViewer.cancel')}
        footer={[
          <Button key="cancel" onClick={() => {
            setUploadModalVisible(false);
            setUploadFileList([]);
          }}>
            {t('filesViewer.cancel')}
          </Button>,
          <Button key="upload" type="primary" loading={uploading} onClick={handleUpload}>
            {t('filesViewer.upload')}
          </Button>,
        ]}
      >
        <div className="space-y-4">
          <AntUpload {...uploadProps}>
            <Button icon={<Upload className="w-4 h-4" />}>{t('filesViewer.selectFiles')}</Button>
          </AntUpload>
        </div>
      </Modal>
    </div>
  );
};

export default FilesViewer; 