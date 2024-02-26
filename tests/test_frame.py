from nanofold.frame import Frame
import pytest
import torch


def test_frame_init():
    with pytest.raises(ValueError):
        Frame(torch.stack([torch.eye(3), torch.eye(3)]), torch.stack([torch.zeros(3)]))
    with pytest.raises(ValueError):
        Frame(torch.stack([torch.ones(3)]), torch.stack([torch.zeros(3)]))
    Frame(torch.stack([torch.eye(3)]), torch.stack([torch.zeros(3)]))


def test_frame_inverse():
    rotations = torch.stack(
        [
            torch.eye(3),
            torch.diag(torch.tensor([2, 0.5, 1])),
            torch.diag(torch.tensor([4, 2, 2])),
        ]
    )
    translations = torch.stack([torch.zeros(3), torch.ones(3), torch.tensor([1, 2, 3])])

    expected_rotations = torch.stack(
        [
            torch.eye(3),
            torch.diag(torch.tensor([0.5, 2, 1])),
            torch.diag(torch.tensor([0.25, 0.5, 0.5])),
        ]
    )
    expected_translations = torch.stack(
        [torch.zeros(3), -torch.tensor([0.5, 2, 1]), -torch.tensor([0.25, 1, 1.5])]
    )
    expected = Frame(expected_rotations, expected_translations)

    frames = Frame(rotations, translations)
    inverse = Frame.inverse(frames)
    assert torch.allclose(
        inverse.rotations, expected.rotations
    ), f"{inverse.rotations} != {expected.rotations}"
    assert torch.allclose(
        inverse.translations, expected.translations
    ), f"{inverse.translations} != {expected.translations}"
