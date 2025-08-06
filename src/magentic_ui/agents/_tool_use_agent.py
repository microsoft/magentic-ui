import json


# define the tool function for tool use agent
def get_user_preferences(user_id: str = "user_001") -> str:
    """
    When booking a flight, using a default user_id;
    Then, get the specific user's preferences and return a json-formatted
    """
    
    mock_preferences = {
        "user_001": {
            "user_id": "user_001",
            "name": "张三",
            "id_number": "44538119900101453X",
            "flight_preferences": {
                "preferred_airlines": ["中国国际航空", "中国南方航空", "中国东方航空"],
                "preferred_seat_class": "经济舱",
                "preferred_seat_location": "靠窗",
                "meal_preference": "素食",
                "baggage_preference": "只带随身行李",
                "preferred_departure_time": "上午",
                "price_sensitivity": "中等",
                "special_assistance": False
            },
            "contact_info": {
                "email": "zhangsan@example.com",
                "phone": "13800138001"
            }
        },
        "user_002": {
            "user_id": "user_002", 
            "name": "李四",
            "flight_preferences": {
                "preferred_airlines": ["海南航空", "深圳航空", "厦门航空"],
                "preferred_seat_class": "商务舱",
                "preferred_seat_location": "过道",
                "meal_preference": "无特殊要求",
                "baggage_preference": "需要托运行李",
                "preferred_departure_time": "下午",
                "price_sensitivity": "低",
                "special_assistance": False
            },
            "contact_info": {
                "email": "lisi@example.com",
                "phone": "13900139001"
            }
        },
        "user_003": {
            "user_id": "user_003",
            "name": "王五", 
            "flight_preferences": {
                "preferred_airlines": ["春秋航空", "吉祥航空", "华夏航空"],
                "preferred_seat_class": "经济舱",
                "preferred_seat_location": "无特殊要求",
                "meal_preference": "无特殊要求",
                "baggage_preference": "只带随身行李",
                "preferred_departure_time": "晚上",
                "price_sensitivity": "高",
                "special_assistance": True,
                "special_assistance_details": "需要轮椅服务"
            },
            "contact_info": {
                "email": "wangwu@example.com",
                "phone": "13700137001"
            }
        }
    }
    
    # Return preferences for the specified user_id, or default if not found
    if user_id in mock_preferences:
        json_formatted_preferences = json.dumps(mock_preferences[user_id])
        return json_formatted_preferences
    else:
        # Return default preferences for unknown users
        default_preferences = {
            "user_id": user_id,
            "name": "张三",
            "flight_preferences": {
                "preferred_airlines": ["中国国际航空", "中国南方航空", "中国东方航空"],
                "preferred_seat_class": "经济舱",
                "preferred_seat_location": "无特殊要求",
                "meal_preference": "无特殊要求",
                "baggage_preference": "只带随身行李",
                "preferred_departure_time": "无特殊要求",
                "price_sensitivity": "中等",
                "frequent_flyer_program": "无",
                "special_assistance": False
            },
            "contact_info": {
                "email": "zhangsan@example.com",
                "phone": "13800138001"
            }
        }
        json_formatted_preferences = json.dumps(default_preferences)
        return json_formatted_preferences


# def get_user_preferences_test(user_id: str):
#     """
#     Mock function to return flight booking preferences for a given user_id.
#     Returns a JSON-formatted dictionary containing user's flight preferences.
    
#     Args:
#         user_id (str): The user ID to get preferences for
        
#     Returns:
#         dict: A dictionary containing the user's flight booking preferences
#     """
#     # Mock data for different users
#     mock_preferences = {
#         "user_001": {
#             "user_id": "user_001",
#             "name": "张三",
#             "flight_preferences": {
#                 "preferred_airlines": ["中国国际航空", "中国南方航空", "中国东方航空"],
#                 "preferred_seat_class": "经济舱",
#                 "preferred_seat_location": "靠窗",
#                 "meal_preference": "素食",
#                 "baggage_preference": "只带随身行李",
#                 "flexible_dates": True,
#                 "preferred_departure_time": "上午",
#                 "price_sensitivity": "中等",
#                 "frequent_flyer_program": "国航知音卡",
#                 "special_assistance": False
#             },
#             "contact_info": {
#                 "email": "zhangsan@example.com",
#                 "phone": "13800138001"
#             }
#         },
#         "user_002": {
#             "user_id": "user_002", 
#             "name": "李四",
#             "flight_preferences": {
#                 "preferred_airlines": ["海南航空", "深圳航空", "厦门航空"],
#                 "preferred_seat_class": "商务舱",
#                 "preferred_seat_location": "过道",
#                 "meal_preference": "无特殊要求",
#                 "baggage_preference": "需要托运行李",
#                 "flexible_dates": False,
#                 "preferred_departure_time": "下午",
#                 "price_sensitivity": "低",
#                 "frequent_flyer_program": "海航金鹏卡",
#                 "special_assistance": False
#             },
#             "contact_info": {
#                 "email": "lisi@example.com",
#                 "phone": "13900139001"
#             }
#         },
#         "user_003": {
#             "user_id": "user_003",
#             "name": "王五", 
#             "flight_preferences": {
#                 "preferred_airlines": ["春秋航空", "吉祥航空", "华夏航空"],
#                 "preferred_seat_class": "经济舱",
#                 "preferred_seat_location": "无特殊要求",
#                 "meal_preference": "无特殊要求",
#                 "baggage_preference": "只带随身行李",
#                 "flexible_dates": True,
#                 "preferred_departure_time": "晚上",
#                 "price_sensitivity": "高",
#                 "frequent_flyer_program": "春秋航空会员",
#                 "special_assistance": True,
#                 "special_assistance_details": "需要轮椅服务"
#             },
#             "contact_info": {
#                 "email": "wangwu@example.com",
#                 "phone": "13700137001"
#             }
#         }
#     }
    
#     # Return preferences for the specified user_id, or default if not found
#     if user_id in mock_preferences:
#         return mock_preferences[user_id]
#     else:
#         # Return default preferences for unknown users
#         return {
#             "user_id": user_id,
#             "name": "未知用户",
#             "flight_preferences": {
#                 "preferred_airlines": ["中国国际航空", "中国南方航空"],
#                 "preferred_seat_class": "经济舱",
#                 "preferred_seat_location": "无特殊要求",
#                 "meal_preference": "无特殊要求",
#                 "baggage_preference": "只带随身行李",
#                 "flexible_dates": True,
#                 "preferred_departure_time": "无特殊要求",
#                 "price_sensitivity": "中等",
#                 "frequent_flyer_program": "无",
#                 "special_assistance": False
#             },
#             "contact_info": {
#                 "email": "unknown@example.com",
#                 "phone": "00000000000"
#             }
#         }