import torch
import argparse
import logging
import coloredlogs
from tqdm import tqdm
from utils import train_helpers
from config import (config as cfg,
                    architecture as arch,
                    data_loaders as dl)

# Setup colorful logging
logger = logging.getLogger(__name__)
coloredlogs.install(fmt='%(levelname)s %(message)s',
                    level='DEBUG',
                    logger=logger)


# noinspection PyShadowingNames
def train(model, optimizer, criterion, resume_from_epoch=0, min_val_loss=1000):
    """
    Train model

    :param model: Model to be trained
    :param optimizer: Method to compute gradients
    :param criterion: Criterion for computing loss
    :param resume_from_epoch: Resume training from this epoch
    :param min_val_loss: Save models with lesser loss on validation set
    """
    model.train()
    train_loader = dl.train_loader
    for epoch in range(resume_from_epoch, cfg.n_epochs):
        logger.info('TRAINING: Epoch {}/{}'.format(epoch+1, cfg.n_epochs))
        running_loss = 0
        pbar = tqdm(total=len(train_loader), desc='Training')
        for steps, sample in enumerate(train_loader):
            if (steps + 1) % cfg.print_freq == 0:
                pbar.update(cfg.print_freq)

            sample['image'] = sample['image'].to(cfg.device)
            sample['label'] = sample['label'].type(torch.LongTensor).to(cfg.device)
            loss = criterion(model(sample['image']), sample['label'])
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            running_loss += loss.item()
        else:
            pbar.close()
            logger.info(f'Epoch done! Loss = {running_loss/len(train_loader)}')

        if epoch % cfg.val_freq == 0:
            logger.info('VALIDATION')
            model.eval()
            val_loss = val(model)
            model.train()
            logger.info(f'Validation loss: {val_loss}')
            if val_loss < min_val_loss:
                train_helpers.save_val_model(model, epoch, optimizer, val_loss, logger)
                min_val_loss = val_loss
            else:
                logger.info('Skipped saving.')
    else:
        train_helpers.save_end_model(model, optimizer, logger)


# noinspection PyShadowingNames
def val(model):
    """
    Validate model

    :param model: Model to be tested
    :return: Validation loss
    """
    model.eval()
    val_loss = 0
    val_loader = dl.val_loader
    pbar = tqdm(total=len(val_loader), desc='Validation')
    for steps, sample in enumerate(val_loader):
        sample['image'] = sample['image'].to(cfg.device)
        sample['label'] = sample['label'].type(torch.LongTensor).to(cfg.device)
        output = model(sample['image'])
        loss = criterion(output, sample['label'])
        val_loss += loss.item()

        if steps % cfg.print_freq == 0:
            pbar.update(cfg.print_freq)
    else:
        pbar.close()
        val_loss /= len(val_loader)
        model.train()
        return val_loss


# noinspection PyShadowingNames
def test(model, test_image):
    """
    Get segmented image from trained model

    :param model: Model generating the mask
    :param test_image: Image whose mask is to be generated
    :return: Segmented image
    """
    model.eval()

    prediction = model(test_image)
    y = prediction.squeeze().permute(1, 2, 0).cpu().numpy()
    logger.info(f'{y}')
    model.train()


if __name__ == '__main__':
    # CLI
    parser = argparse.ArgumentParser(description=f'CLI for {arch.model_name}')
    parser.add_argument('--phase',
                        type=str,
                        default='train',
                        help='set phase[train(includes val)/test]')
    parser.add_argument('--load',
                        dest='load',
                        action='store_true',
                        help='load model from checkpoints/model.pth')
    parser.set_defaults(load=True)
    args = parser.parse_args()

    # Load values from config file
    # TODO Load from checkpoint if --load
    model = arch.model.to(cfg.device)
    optimizer = arch.optimizer
    criterion = arch.criterion
    resume_from_epoch = cfg.resume_from_epoch
    min_val_loss = cfg.min_val_loss
    device = cfg.device

    if args.load:
        # Load values from checkpoint file
        checkpoint = torch.load(cfg.model_path)
        model.load_state_dict(checkpoint['model_state_dict'])
        optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        resume_from_epoch = checkpoint['epoch']
        min_val_loss = checkpoint['val_loss']

    if args.phase == 'train':
        # Train & periodically validate model
        train(model, optimizer, criterion, resume_from_epoch, min_val_loss)

    elif args.phase == 'test':
        # Test model
        tl = iter(dl.test_loader)
        test_image = next(tl)['image']
        test(model, test_image)

    else:
        raise ValueError('Choose one of train/test.')
