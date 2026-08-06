"""
Kafka消息队列客户端
提供生产者和消费者封装
"""
import json
import logging
from typing import Optional, Callable, Dict, Any
from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import KafkaError

from ..config.settings import settings

logger = logging.getLogger(__name__)

# 全局生产者实例
_producer: Optional[KafkaProducer] = None


def get_kafka_producer() -> KafkaProducer:
    """获取Kafka生产者（单例模式）"""
    global _producer
    if _producer is None:
        try:
            bootstrap_servers = settings.KAFKA_BOOTSTRAP_SERVERS.split(",")
            _producer = KafkaProducer(
                bootstrap_servers=bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                client_id=settings.KAFKA_CLIENT_ID,
                acks='all',  # 等待所有副本确认
                retries=3,
                max_in_flight_requests_per_connection=1,
            )
            logger.info(f"Kafka producer initialized: {bootstrap_servers}")
        except Exception as e:
            logger.error(f"Failed to initialize Kafka producer: {e}")
            if settings.is_production:
                raise
    return _producer


def get_kafka_consumer(
    topic: str,
    group_id: str,
    auto_offset_reset: str = 'latest'
) -> KafkaConsumer:
    """获取Kafka消费者"""
    try:
        bootstrap_servers = settings.KAFKA_BOOTSTRAP_SERVERS.split(",")
        consumer = KafkaConsumer(
            topic,
            bootstrap_servers=bootstrap_servers,
            group_id=group_id,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            key_deserializer=lambda k: k.decode('utf-8') if k else None,
            auto_offset_reset=auto_offset_reset,
            enable_auto_commit=True,
            consumer_timeout_ms=1000,  # 1秒超时
        )
        logger.info(f"Kafka consumer initialized: topic={topic}, group_id={group_id}")
        return consumer
    except Exception as e:
        logger.error(f"Failed to initialize Kafka consumer: {e}")
        if settings.is_production:
            raise
        return None


def publish_message(topic: str, message: Dict[str, Any], key: Optional[str] = None) -> bool:
    """发布消息到Kafka"""
    try:
        producer = get_kafka_producer()
        if producer is None:
            logger.error("Kafka producer not available")
            return False
        
        future = producer.send(topic, value=message, key=key)
        # 等待消息发送完成
        record_metadata = future.get(timeout=10)
        logger.info(
            f"Message published successfully: topic={record_metadata.topic}, "
            f"partition={record_metadata.partition}, offset={record_metadata.offset}"
        )
        return True
    except KafkaError as e:
        logger.error(f"Failed to publish message to Kafka: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error publishing message: {e}")
        return False


def consume_messages(
    topic: str,
    group_id: str,
    handler: Callable[[Dict[str, Any]], None],
    auto_offset_reset: str = 'latest'
) -> None:
    """消费Kafka消息"""
    consumer = get_kafka_consumer(topic, group_id, auto_offset_reset)
    if consumer is None:
        logger.error("Kafka consumer not available")
        return
    
    try:
        logger.info(f"Starting to consume messages from topic: {topic}")
        for message in consumer:
            try:
                handler(message.value)
            except Exception as e:
                logger.error(f"Error handling message: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Error consuming messages: {e}", exc_info=True)
    finally:
        consumer.close()

