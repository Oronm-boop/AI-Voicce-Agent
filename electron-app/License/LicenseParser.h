#ifndef LICENSE_PARSER_H
#define LICENSE_PARSER_H

#include <windows.h>
#include <time.h>
#include <string>

// 导出宏：DLL 导出时定义 LICENSE_PARSER_EXPORTS
#ifdef LICENSE_PARSER_EXPORTS
#define LICENSE_API __declspec(dllexport)
#else
#define LICENSE_API __declspec(dllimport)
#endif

// 错误码定义（供外部判断失败原因）
typedef enum {
	LICENSE_SUCCESS = 0,
	LICENSE_INVALID_FORMAT,    // 格式错误
	LICENSE_DECRYPT_FAILED,    // 解密失败
	LICENSE_CHECKSUM_ERROR,    // 校验和错误
	LICENSE_DEVICE_MISMATCH,   // 设备不匹配
	LICENSE_EXPIRED,           // 已过期
	LICENSE_ABSENT,     //License缺失
	LICENSE_CONNECT_FAILED  // 连接失败
} LicenseStatus;

// License 信息结构体（供外部获取解析结果）
typedef struct {
	time_t expiryDate;         // 过期时间
	char vendor[256];          // 主板制造商（UTF-8）
	char name[256];            // 主板型号（UTF-8）
	char macAddress[64];       // 匹配的 MAC 地址（UTF-8）
} LicenseInfo;

#ifdef __cplusplus
extern "C" {
#endif

	/**
	 * 解析并验证 License 数据
	 * @param info 输出参数：解析后的 License 信息（成功时有效）ip port
	 */
	LICENSE_API bool __stdcall ParseAndVerifyLicense(const char* ip, int port);

	/**
	 * 获取当前设备的硬件信息（用于生成 License 时参考）
	 * @param vendor 输出：主板制造商（UTF-8，缓冲区至少 256 字节）
	 * @param name 输出：主板型号（UTF-8，缓冲区至少 256 字节）
	 * @param macs 输出：MAC 地址列表（UTF-8，分号分隔，缓冲区至少 1024 字节）
	 * @return 是否成功（true/false）
	 */
	LICENSE_API bool __stdcall GetDeviceInfo(char* vendor, char* name, char* macs);


#ifdef __cplusplus
}
#endif

#endif // LICENSE_PARSER_H