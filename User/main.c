#include "system.h"
#include "SysTick.h"
#include "led.h"
#include "usart.h"
#include "tftlcd.h"
#include <stdio.h>

#define FACE_IMG_W 64
#define FACE_IMG_H 64
#define FACE_IMG_SIZE 8192

// 这两个变量必须是全局的，供 USART1_IRQHandler 使用
u8 face_img_buf[FACE_IMG_SIZE];
volatile u8 face_frame_ready = 0;

/*
    ==================================================
    图像放大显示函数 (2倍放大至128x128)
    ==================================================
*/
void LCD_ShowPicture_Zoom(u16 x, u16 y, u16 width, u16 height, u8 *pic, u8 scale)
{
    u16 i, j;
    u16 color;
    
    for (i = 0; i < height; i++)
    {
        for (j = 0; j < width; j++)
        {
            color = (pic[(i * width + j) * 2] << 8) | pic[(i * width + j) * 2 + 1];
            LCD_Fill(x + j * scale, 
                     y + i * scale, 
                     x + j * scale + scale - 1, 
                     y + i * scale + scale - 1, 
                     color);
        }
    }
}

int main(void)
{
    SysTick_Init(72);
    NVIC_PriorityGroupConfig(NVIC_PriorityGroup_2);

    // 【关键】：波特率改到了 460800，极大提升吞吐量
    USART1_Init(115200);

    LED_Init();
    TFTLCD_Init();

    FRONT_COLOR = BLACK;
    LCD_Clear(WHITE);

    LCD_ShowString(20, 10, 220, 24, 24, (u8 *)"Direct Serial Face");
    LCD_ShowString(20, 45, 240, 16, 16, (u8 *)"Baud: 460800 bps");
    LCD_ShowString(20, 75, 240, 16, 16, (u8 *)"Status: Waiting Data...");

    // 绘制图片底框预留位置，128x128，居中x=56
    LCD_Fill(56, 120, 56 + FACE_IMG_W * 2, 120 + FACE_IMG_H * 2, GRAY);

    while (1)
    {
        // 串口中断会在后台默默把数组填满，填满后将标记置 1
        if (face_frame_ready == 1)
        {
            // 收到一帧完整图像，进行放大显示
            LCD_ShowPicture_Zoom(56, 120, FACE_IMG_W, FACE_IMG_H, face_img_buf, 2);
            
            // 显示完清除标记，等待接收下一帧
            face_frame_ready = 0;
            
            // 翻转LED代表正在流畅运行
            LED1 = !LED1; 
        }
    }
}