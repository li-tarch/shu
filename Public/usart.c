#include "usart.h"
#include "string.h"  // 添加字符串处理头文件	
#include "stm32f10x.h"  // 包含STM32F10x的头文件
#include "stm32f10x_usart.h"  // 包含USART相关的头文件
#include "stm32f10x_gpio.h"  // 包含GPIO相关的头文件
 

int fputc(int ch,FILE *p)  //函数默认的，在使用printf函数时自动调用
{
	USART_SendData(USART1,(u8)ch);	
	while(USART_GetFlagStatus(USART1,USART_FLAG_TXE)==RESET);
	return ch;
}

//使用scanf时需要关闭USART1中断功能
//重定向c库函数scanf到USART1
int fgetc(FILE *f)
{
	/* 等待串口1输入数据 */
	while (USART_GetFlagStatus(USART1, USART_FLAG_RXNE) == RESET);

	return (int)USART_ReceiveData(USART1);
}

//串口1中断服务程序
//注意,读取USARTx->SR能避免莫名其妙的错误   	
u8 USART1_RX_BUF[USART1_REC_LEN];     //接收缓冲,最大USART_REC_LEN个字节.
//接收状态
//bit15，	接收完成标志
//bit14，	接收到0x0d
//bit13~0，	接收到的有效字节数目
u16 USART1_RX_STA=0;       //接收状态标记


/*******************************************************************************
* 函 数 名         : USART1_Init
* 函数功能		   : USART1初始化函数
* 输    入         : bound:波特率
* 输    出         : 无
*******************************************************************************/ 
void USART1_Init(u32 bound)
{
   //GPIO端口设置
	GPIO_InitTypeDef GPIO_InitStructure;
	USART_InitTypeDef USART_InitStructure;
	NVIC_InitTypeDef NVIC_InitStructure;
	
	RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOA,ENABLE);
	RCC_APB2PeriphClockCmd(RCC_APB2Periph_USART1,ENABLE);
 
	
	/*  配置GPIO的模式和IO口 */
	GPIO_InitStructure.GPIO_Pin=GPIO_Pin_9;//TX			   //串口输出PA9
	GPIO_InitStructure.GPIO_Speed=GPIO_Speed_50MHz;
	GPIO_InitStructure.GPIO_Mode=GPIO_Mode_AF_PP;	    //复用推挽输出
	GPIO_Init(GPIOA,&GPIO_InitStructure);  /* 初始化串口输入IO */
	GPIO_InitStructure.GPIO_Pin=GPIO_Pin_10;//RX			 //串口输入PA10
	GPIO_InitStructure.GPIO_Mode=GPIO_Mode_IN_FLOATING;		  //模拟输入
	GPIO_Init(GPIOA,&GPIO_InitStructure); /* 初始化GPIO */
	

	//USART1 初始化设置
	USART_InitStructure.USART_BaudRate = bound;//波特率设置
	USART_InitStructure.USART_WordLength = USART_WordLength_8b;//字长为8位数据格式
	USART_InitStructure.USART_StopBits = USART_StopBits_1;//一个停止位
	USART_InitStructure.USART_Parity = USART_Parity_No;//无奇偶校验位
	USART_InitStructure.USART_HardwareFlowControl = USART_HardwareFlowControl_None;//无硬件数据流控制
	USART_InitStructure.USART_Mode = USART_Mode_Rx | USART_Mode_Tx;	//收发模式
	USART_Init(USART1, &USART_InitStructure); //初始化串口1
	
	USART_Cmd(USART1, ENABLE);  //使能串口1 
	
	USART_ClearFlag(USART1, USART_FLAG_TC);
		
	// 启用接收中断
	USART_ITConfig(USART1, USART_IT_RXNE, ENABLE);

	//Usart1 NVIC 配置
	NVIC_InitStructure.NVIC_IRQChannel = USART1_IRQn;//串口1中断通道
	NVIC_InitStructure.NVIC_IRQChannelPreemptionPriority=3;//抢占优先级3
	NVIC_InitStructure.NVIC_IRQChannelSubPriority =3;		//子优先级3
	NVIC_InitStructure.NVIC_IRQChannelCmd = ENABLE;			//IRQ通道使能
	NVIC_Init(&NVIC_InitStructure);	//根据指定的参数初始化VIC寄存器、	
}
/*******************************************************************************
* 函 数 名         : USART1_IRQHandler
* 函数功能		   : USART1中断函数
* 输    入         : 无
* 输    出         : 无
*******************************************************************************/ 
// 注意: 该函数会在USART1接收到数据时被调用



// 假设这些宏定义已经存在于合适的地方

// extern vu16 USART1_RX_STA; // 接收状态标记
// extern u8 USART1_RX_BUF[]; // 接收缓冲区


/* ==================================================
   放在 usart.c 或者 stm32f10x_it.c 的末尾或替换原有中断
   ================================================== */
/* ==================================================
   放在 usart.c 或者 stm32f10x_it.c 的末尾
   ================================================== */
extern u8 face_img_buf[8192];
extern volatile u8 face_frame_ready; // 注意 main.c 里也要加上 volatile 关键字

u32 face_rx_cnt = 0;
u8 face_rx_state = 0;

void USART1_IRQHandler(void)
{
    u8 res;
    
    // 【防护 1】：清除 ORE (Overrun Error) 溢出错误，防止单片机遇难彻底卡死
    if(USART_GetFlagStatus(USART1, USART_FLAG_ORE) != RESET)
    {
        res = USART_ReceiveData(USART1); 
    }

    if(USART_GetITStatus(USART1, USART_IT_RXNE) != RESET)
    {
        res = USART_ReceiveData(USART1);
        
        // 【防护 2】：如果主循环还没把上一张图画完，直接丢弃新来的数据
        // 就像你还在吃饭，别人接着给你塞，你必须拒绝，否则会吐（花屏/白屏）
        if(face_frame_ready == 1)
        {
            face_rx_state = 0;
            return;
        }
        
        // 状态机：寻找同步头 0x5A, 0xA5, 0xAA, 0x55
        if(face_rx_state == 0 && res == 0x5A) face_rx_state = 1;
        else if(face_rx_state == 1 && res == 0xA5) face_rx_state = 2;
        else if(face_rx_state == 2 && res == 0xAA) face_rx_state = 3;
        else if(face_rx_state == 3 && res == 0x55) 
        {
            face_rx_state = 4;
            face_rx_cnt = 0; 
        }
        else if(face_rx_state == 4) 
        {
            face_img_buf[face_rx_cnt++] = res;
            if(face_rx_cnt >= 8192) 
            {
                face_frame_ready = 1; // 通知 main 函数去刷新屏幕
                face_rx_state = 0;    // 等待下一帧的同步头
            }
        }
        else 
        {
            face_rx_state = 0; 
        }
    } 
}